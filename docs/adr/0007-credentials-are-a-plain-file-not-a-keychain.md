# Credentials are a plain file, not an OS keychain

The credential store is a single TOML file under the user's data directory,
created mode 0600, holding secrets in plain text. `tp` ships no integration
with the macOS Keychain, the Windows Credential Manager, or the Secret Service
API. A user who wants their secrets held by one of those points a value
expression's command form at its CLI.

## Why

`tp` executes arbitrary commands and reads arbitrary files on the user's
behalf. That is the product, stated plainly in the brief, which also says not
to pretend otherwise or add theatrical guardrails.

Given that, ask what a keychain would defend against. Not another process
running as the user: it can run `tp` itself, or read the config that says where
the secrets come from, or attach to the process. Not a stolen disk: that is
full-disk encryption's job, and the keychain's at-rest protection on the common
platforms is derived from the login password the attacker has already had to
defeat. Not an attacker who has the user's shell: they have the key.

What it *would* defend against is a careless `cat` of the file in a screen
share, and someone else's backup tool sweeping up a dotfile. Those are real.
They are also exactly what the command form addresses, at a fraction of the
cost and without `tp` owning the answer: `pass`, `op`, `gopass`, `vault` and
the platform keychain CLIs all already exist, all already solve this, and all
already have the user's trust in a way a coding agent's first-party keychain
integration would have to earn.

The cost side is not small. Three platform backends, each with its own prompt
behaviour, its own failure modes when the session is not unlocked, and its own
degradation story over SSH — where a headless session cannot unlock a keychain
at all, and the fallback would be a plain file anyway. That is a large,
permanently-maintained surface whose ceiling is the security of the thing it
falls back to.

The honest position is to store secrets plainly, say so, and make the good
alternative a one-line config change.

## Considered options

- **OS keychain with a plain-file fallback.** Rejected above: the fallback is
  where headless and SSH sessions live, so the plain file is on the main path
  regardless, and the keychain becomes a second path that is exercised less and
  trusted more.
- **Encrypt the file with a passphrase.** Rejected: a long-lived agent process
  would have to hold the passphrase in memory for the life of the session, or
  prompt mid-request, which is the worst moment. It converts a storage problem
  into a session-management problem and ends with the key in memory anyway.
- **No credential store at all — environment and commands only.** Seriously
  considered, and it is close to right. Rejected because the brief's precedence
  ladder names a credential store as a distinct tier, and because a first-run
  user pasting a key needs somewhere for it to go that survives the session.

## Consequences

The file's permissions are the whole of its protection, so `tp` sets 0600 on
create and refuses to read a store that is group- or world-readable, naming the
file and the fix. A permissive mode is a configuration error, not a warning.

Documentation states in plain words that credentials are stored unencrypted and
points at the command form. This is a place where an accurate sentence is worth
more than a reassuring one.

Nothing in the codebase gains a dependency on a platform secrets API, which
keeps the credential path identical on every platform and under SSH — the same
property that made the fallback the main path in the first place.
