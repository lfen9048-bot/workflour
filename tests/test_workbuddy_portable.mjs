import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
const moduleUrl = new URL('../integrations/openmausbot/workbuddy/client.mjs', import.meta.url).href;
function probe(env) {
  return spawnSync(process.execPath, ['--input-type=module', '-e',
    `const m=await import(${JSON.stringify(moduleUrl)}); console.log(JSON.stringify([m.DEFAULT_PATCH_PATH,m.DEFAULT_PACKAGE_DIR]))`],
    {env: {...process.env, ...env}, encoding:'utf8'});
}
test('Ubuntu cost routing and check-in use the chosen local Web profile without reading credentials', () => {
  const result = probe({DSH_HOME:'/tmp/linux dsh',WORKFLOUR_DSH_SOURCE_PROFILE:'web'});
  assert.equal(result.status,0,result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), ['/tmp/linux dsh/profiles/web/cordis.patch.yml',
    '/tmp/linux dsh/profiles/web/node_modules/dsh-connect-workbuddy']);
});
test('Mac default remains desktop, with explicit DSH_HOME honored', () => {
  const result = probe({DSH_HOME:'/tmp/my-dsh',WORKFLOUR_DSH_SOURCE_PROFILE:''});
  assert.equal(result.status,0,result.stderr);
  assert.equal(JSON.parse(result.stdout)[0],'/tmp/my-dsh/profiles/desktop/cordis.patch.yml');
});
test('invalid profile cannot escape the profiles directory', () => {
  const result=probe({DSH_HOME:'/tmp/dsh',WORKFLOUR_DSH_SOURCE_PROFILE:'../secrets'});
  assert.notEqual(result.status,0);
  assert.equal(result.stdout,'');
  assert.match(result.stderr,/Invalid WorkBuddy source profile/);
});
