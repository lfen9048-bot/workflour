#!/usr/bin/env ruby
# Project-only startup overlay for WorkBuddy 5.13.1 pool preferences.
# Reuses the plugin's native member/order/enabled fields; it does not route
# requests or read the credential vault. Native Cordis patches replace config
# wholesale, so preserve the TARGET config and replace only the three fields.
require 'yaml'
require 'json'
require 'digest'
require 'fileutils'
require 'optparse'
require 'securerandom'
require 'tempfile'

module WorkflourPoolSync
  ROLES = %w[omb-wf-manager omb-wf-plan-lead omb-wf-plan-review
             omb-wf-code-review omb-wf-code-helper omb-wf-assistant].freeze
  POOL_FIELDS = %w[enabled memberAccountIds orderAccountIds].freeze
  SECRET_FIELDS = /\A(?:access[_-]?token|refresh[_-]?token|api[_-]?key|token|secret|password|authorization)\z/i

  class Invalid < StandardError; end

  def self.read_entry(path)
    raise Invalid, 'config file is missing' unless File.file?(path)
    tree = YAML.safe_load(File.read(path), permitted_classes: [], permitted_symbols: [], aliases: false)
    raise Invalid, 'expected a patch list' unless tree.is_a?(Array)
    rows = tree.select { |row| row.is_a?(Hash) && row['id'] == 'dsh-connect-workbuddy' }
    raise Invalid, 'expected exactly one WorkBuddy config entry' unless rows.length == 1 && rows[0]['config'].is_a?(Hash)
    rows[0]['config']
  rescue Psych::Exception, EncodingError
    # YAML exceptions may quote source text, which may contain account data.
    raise Invalid, 'config cannot be parsed safely'
  end

  def self.ids(value)
    unless value.is_a?(Array) && value.all? { |id| id.is_a?(String) && /\A[0-9a-f]{24}\z/.match?(id) } && value.uniq.length == value.length
      raise Invalid, 'pool members/order must contain unique native account IDs'
    end
    value
  end

  def self.preferences(config)
    regions = config['regions']
    raise Invalid, 'desktop region preferences are missing' unless regions.is_a?(Hash)
    %w[cn global].each_with_object({}) do |region, result|
      region_config = regions[region]
      raise Invalid, 'desktop region preferences are missing' unless region_config.is_a?(Hash)
      pool = region_config['pool']
      raise Invalid, 'desktop pool preferences are missing' unless pool.is_a?(Hash)
      enabled = pool['enabled']
      raise Invalid, 'pool enabled must be boolean' unless enabled == true || enabled == false
      members = ids(pool.fetch('memberAccountIds', []))
      order = ids(pool.fetch('orderAccountIds', []))
      raise Invalid, 'pool order contains an unchecked member' unless (order - members).empty?
      raise Invalid, 'enabled pool has no checked members' if enabled && members.empty?
      result[region] = { 'enabled' => enabled, 'memberAccountIds' => members, 'orderAccountIds' => order }
    end
  end

  def self.assert_no_credentials(value)
    case value
    when Hash
      raise Invalid, 'inline credentials are not supported by the startup overlay' if value.keys.any? { |key| SECRET_FIELDS.match?(key.to_s) }
      value.each_value { |child| assert_no_credentials(child) }
    when Array
      value.each { |child| assert_no_credentials(child) }
    end
  end

  def self.compose(target, prefs)
    assert_no_credentials(target)
    result = JSON.parse(JSON.generate(target))
    regions = result['regions']
    raise Invalid, 'target region config is missing' unless regions.is_a?(Hash)
    prefs.each do |region, pool_prefs|
      raise Invalid, 'target region config is missing' unless regions[region].is_a?(Hash)
      pool = regions[region]['pool']
      raise Invalid, 'target pool config must be an object' unless pool.nil? || pool.is_a?(Hash)
      regions[region]['pool'] = (pool || {}).merge(pool_prefs)
    end
    [{ 'id' => 'dsh-connect-workbuddy', 'config' => result }]
  end

  def self.private_dir(path)
    raise Invalid, 'overlay directory must not be a symlink' if File.symlink?(path)
    FileUtils.mkdir_p(path, mode: 0700)
    raise Invalid, 'overlay directory has a different owner' unless File.stat(path).uid == Process.uid
    File.chmod(0700, path)
  end

  def self.alive?(pid)
    Process.kill(0, pid)
    true
  rescue Errno::ESRCH
    false
  rescue Errno::EPERM
    true
  end

  def self.atomic_write(path, contents)
    Tempfile.create(['.pool-', '.tmp'], File.dirname(path), mode: 0600) do |file|
      file.chmod(0600)
      file.write(contents)
      file.flush
      file.fsync
      File.rename(file.path, path)
    end
  end

  def self.prepare(home, profile, prefs, owner_pid)
    raise Invalid, 'owner process is not alive' unless owner_pid > 1 && alive?(owner_pid)
    target = read_entry(File.join(home, 'profiles', profile, 'cordis.patch.yml'))
    overlay = compose(target, prefs)
    base = File.join(home, 'workflour-pool-overlays')
    private_dir(base)
    dir = File.join(base, profile)
    private_dir(dir)
    # Each ACP process owns a different layer. The plugin can update its layer
    # without racing another process or overwriting the desktop settings.
    # Remove only our files belonging to dead owners on the next startup.
    Dir.children(dir).each do |name|
      match = /\Apool-(\d+)-[0-9a-f]{16}\.yml(?:\.meta\.json)?\z/.match(name)
      next unless match && !alive?(match[1].to_i)
      path = File.join(dir, name)
      File.unlink(path) if File.file?(path) && !File.symlink?(path)
    end
    path = File.join(dir, "pool-#{owner_pid}-#{SecureRandom.hex(8)}.yml")
    summary = {
      version: 1, profile: profile, owner_pid: owner_pid,
      source: 'profiles/desktop/cordis.patch.yml',
      preference_sha256: Digest::SHA256.hexdigest(JSON.generate(prefs)),
      regions: prefs.transform_values { |pool| { enabled: pool['enabled'], members: pool['memberAccountIds'].length, ordered: pool['orderAccountIds'].length } },
      precedence: 'target WorkBuddy config plus desktop pool preferences; later independent title/fallback layers remain intact'
    }
    atomic_write(path, YAML.dump(overlay))
    begin
      atomic_write(path + '.meta.json', JSON.pretty_generate(summary) + "\n")
    rescue StandardError
      File.unlink(path)
      raise
    end
    warn 'workflour-pool-sync: ' + JSON.generate(summary.slice(:profile, :regions, :preference_sha256))
    path
  end

  def self.main(argv)
    options = { home: ENV.fetch('DSH_HOME', File.join(Dir.home, '.dsh')), owner_pid: Process.ppid }
    parser = OptionParser.new do |opts|
      opts.banner = 'Usage: workbuddy-pool-sync.rb --profile omb-wf-ROLE --check|--prepare [--home PATH] [--owner-pid PID]'
      opts.on('--profile NAME') { |value| options[:profile] = value }
      opts.on('--home PATH') { |value| options[:home] = value }
      opts.on('--owner-pid PID', Integer) { |value| options[:owner_pid] = value }
      opts.on('--check') { raise Invalid, 'select one operation' if options[:mode]; options[:mode] = :check }
      opts.on('--prepare') { raise Invalid, 'select one operation' if options[:mode]; options[:mode] = :prepare }
    end
    parser.parse!(argv)
    raise Invalid, 'unsupported profile or operation' unless argv.empty? && ROLES.include?(options[:profile]) && options[:mode]
    home = File.expand_path(options[:home])
    prefs = preferences(read_entry(File.join(home, 'profiles/desktop/cordis.patch.yml')))
    if options[:mode] == :check
      puts JSON.generate({ profile: options[:profile], source_valid: true, regions: prefs.transform_values { |pool| { enabled: pool['enabled'], members: pool['memberAccountIds'].length, ordered: pool['orderAccountIds'].length } } })
    else
      puts prepare(home, options[:profile], prefs, options[:owner_pid])
    end
    0
  rescue Invalid => error
    warn "workflour-pool-sync: #{error.message}; refusing to start with stale account-pool settings"
    1
  rescue OptionParser::ParseError, SystemCallError, IOError
    warn 'workflour-pool-sync: config/overlay I/O or arguments failed; refusing to start with stale account-pool settings'
    1
  end
end

exit WorkflourPoolSync.main(ARGV) if $PROGRAM_NAME == __FILE__
