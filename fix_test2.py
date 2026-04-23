import re

# Fix arena/src/test.rs
f = "contract/arena/src/test.rs"
with open(f, "r") as file:
    content = file.read()
content = content.replace("&DataKey::Admin", "&symbol_short!(\"ADMIN\")")
with open(f, "w") as file:
    file.write(content)

# Fix arena/src/commit_reveal_tests.rs
f = "contract/arena/src/commit_reveal_tests.rs"
with open(f, "r") as file:
    content = file.read()
content = content.replace("commit_deadline_ledger", "round_deadline_ledger")
content = re.sub(r"(&nonce.*?)(\s*\))", r"\1.clone().into()\2", content)
with open(f, "w") as file:
    file.write(content)

# Fix arena/src/expire_arena_tests.rs
f = "contract/arena/src/expire_arena_tests.rs"
with open(f, "r") as file:
    content = file.read()
content = content.replace("env.register_stellar_asset_contract(token_admin.clone());", "env.register_stellar_asset_contract_v2(token_admin.clone()).address();")
with open(f, "w") as file:
    file.write(content)

# Fix arena/src/mutation_tests.rs
f = "contract/arena/src/mutation_tests.rs"
with open(f, "r") as file:
    content = file.read()
content = content.replace("let result = Err(Ok(ArenaError::AlreadyInitialized));", "let result: Result<(), Result<ArenaError, _>> = Err(Ok(ArenaError::AlreadyInitialized));")
with open(f, "w") as file:
    file.write(content)

