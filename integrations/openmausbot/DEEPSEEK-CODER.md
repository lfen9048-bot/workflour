# Independent DeepSeek coding role

The new role uses the existing Harness binary, WorkBuddy account and ACP resume
bridge. It has its own profile and automatically advertised skill. This is role
configuration, not a filesystem sandbox.

Generate only this role and its OpenMausBot instance:

```sh
./integrations/openmausbot/setup.sh --only deepseek-coder
```

This creates `~/.dsh/profiles/omb-deepseek-coder` and the `omb-deepseek-coder`
instance. It does not create a Bot or send a prompt. Existing Coder, Doc and
Antigravity profiles/instances stay as they are. The no-argument setup command
retains its original scope. Account state is copied from the existing Doc profile
on first setup, then the new role's own current state is preserved on subsequent
runs. Credentials stay outside the repository; new runtime files are private.

Launcher and optional real protocol check:

```sh
./run-acp-agent.sh deepseek-coder --version
python3 tests/acp-smoke.py deepseek-coder
```

The smoke check creates a native session and can refresh account/model metadata;
it sends no model prompt. Creating a Bot and validating real consultation are
separate steps. Use a fresh task for coding instead of continuing a Doc thread.

Offline setup regression tests use temporary fake homes and dummy account data:

```sh
python3 -m unittest discover -s tests -p 'test_deepseek_coder_setup.py' -v
```
