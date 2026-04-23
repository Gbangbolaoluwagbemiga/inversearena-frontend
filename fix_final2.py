import re

# 1. lib.rs
f = "contract/arena/src/lib.rs"
with open(f, "r") as file:
    content = file.read()

# Add IntoVal
if "IntoVal" not in content:
    content = content.replace("Address, Bytes,", "IntoVal, Address, Bytes,")

# ensure arena_id is u64
content = re.sub(r"let arena_id\s*=\s*env\.storage\(\)\.instance\(\)\.get\(&DataKey::ArenaId\)\.unwrap_or\(0\);",
                 "let arena_id: u64 = env.storage().instance().get(&DataKey::ArenaId).unwrap_or(0);", content)

with open(f, "w") as file:
    file.write(content)

# 2. commit_reveal_tests.rs
f = "contract/arena/src/commit_reveal_tests.rs"
with open(f, "r") as file:
    content = file.read()

# Clean up the mess from previous regex
content = re.sub(r"&\(nonce\.clone\(\)\.into\(\)\)\.clone\(\)\.into\(\)", r"&Bytes::from_slice(&env, &nonce.to_array())", content)
content = re.sub(r"&\(nonce1\.clone\(\)\.into\(\)\)\.clone\(\)\.into\(\)", r"&Bytes::from_slice(&env, &nonce1.to_array())", content)
content = re.sub(r"&\(nonce2\.clone\(\)\.into\(\)\)\.clone\(\)\.into\(\)", r"&Bytes::from_slice(&env, &nonce2.to_array())", content)
content = re.sub(r"&\(wrong_nonce\.clone\(\)\.into\(\)\)\.clone\(\)\.into\(\)", r"&Bytes::from_slice(&env, &wrong_nonce.to_array())", content)
content = re.sub(r"&\(BytesN::from_array\(&env, &\[0; 32\]\)\)\.clone\(\)\.into\(\)", r"&Bytes::from_slice(&env, &[0; 32])", content)

with open(f, "w") as file:
    file.write(content)

# 3. mutation_tests.rs
f = "contract/arena/src/mutation_tests.rs"
with open(f, "r") as file:
    content = file.read()

content = content.replace("let result: Result<(), Result<crate::ArenaError, _>> = Err(Ok(crate::ArenaError::AlreadyInitialized));", "let result: Result<(), Result<crate::ArenaError, soroban_sdk::InvokeError>> = Err(Ok(crate::ArenaError::AlreadyInitialized));")

with open(f, "w") as file:
    file.write(content)

