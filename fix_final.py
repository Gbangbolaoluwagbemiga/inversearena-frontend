import re

# 1. lib.rs fixes
f = "contract/arena/src/lib.rs"
with open(f, "r") as file:
    content = file.read()
# Fix type of arena_id:
content = content.replace("let arena_id = env.storage().instance().get(&DataKey::ArenaId).unwrap_or(0);", "let arena_id: u64 = env.storage().instance().get(&DataKey::ArenaId).unwrap_or(0);")
# Fix init
content = content.replace("client.init(&10u32, &100i128);", "client.init(&10u32, &100i128, &3600);")
with open(f, "w") as file:
    file.write(content)

# 2. commit_reveal_tests.rs fixes
f = "contract/arena/src/commit_reveal_tests.rs"
with open(f, "r") as file:
    content = file.read()
content = content.replace("commit_deadline_ledger", "round_deadline_ledger")
content = content.replace("reveal_deadline_ledger", "round_deadline_ledger")

# reveal_choice takes &Bytes, so we convert from BytesN<32>
content = re.sub(r"reveal_choice\((.*?), (.*?), (.*?), &(.*?)\);", r"reveal_choice(\1, \2, \3, &(\4).clone().into());", content)

with open(f, "w") as file:
    file.write(content)

# 3. mutation_tests.rs fixes
f = "contract/arena/src/mutation_tests.rs"
with open(f, "r") as file:
    content = file.read()
content = content.replace("let result: Result<(), Result<ArenaError, _>> = Err(Ok(ArenaError::AlreadyInitialized));", "let result: Result<(), Result<crate::ArenaError, _>> = Err(Ok(crate::ArenaError::AlreadyInitialized));")
# The compiler error was `cannot infer type of the type parameter E declared on the enum Result`
# To fix: `let result: Result<(), Result<ArenaError, soroban_sdk::InvokeError>> = Err(Ok(ArenaError::AlreadyInitialized));`
content = content.replace("Result<ArenaError, _>", "Result<ArenaError, soroban_sdk::InvokeError>")

with open(f, "w") as file:
    file.write(content)

