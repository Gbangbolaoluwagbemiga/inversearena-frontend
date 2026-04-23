import re

f = "contract/arena/src/lib.rs"
with open(f, "r") as file:
    content = file.read()

# 1. Add NotWhitelisted
content = content.replace("HashMismatch = 45,\n}", "HashMismatch = 45,\n    NotWhitelisted = 46,\n}")

# 2. Add is_private
content = content.replace("    pub win_fee_bps: u32,\n}", "    pub win_fee_bps: u32,\n    pub is_private: bool,\n}")

# 3. Add DataKey variants
content = content.replace("    Metadata(u64),\n}", "    Metadata(u64),\n    ArenaId,\n    FactoryAddress,\n}")

# 4. Remove duplicate set_max_rounds, is_cancelled, and leave
# I will use a regex to find them, or since I know they appear twice, I can replace the second ones or first ones.
# Actually let's just find `pub fn set_max_rounds` and remove the first occurrence.
# The `git diff` showed it was removed around line 584:
content = re.sub(r"    pub fn set_max_rounds\(env: Env, max_rounds: u32\) -> Result<\(\), ArenaError> \{.*?Ok\(\(\)\)\n    \}", "", content, flags=re.DOTALL, count=1)
content = re.sub(r"    pub fn is_cancelled\(env: Env\) -> bool \{.*?\}", "", content, flags=re.DOTALL, count=1)
content = re.sub(r"    pub fn leave\(env: Env, player: Address\) -> Result<i128, ArenaError> \{.*?\+ amount\)\);\n        Ok\(\(\)\)\n    \}", "", content, flags=re.DOTALL, count=1)

# 5. Replace get_state with state
content = content.replace("get_state(&env)", "state(&env)")
# Fix set_state(&env, ArenaState::Cancelled); to env.storage().instance().set(&STATE_KEY, &ArenaState::Cancelled);
content = content.replace("set_state(&env, ArenaState::Cancelled);", "env.storage().instance().set(&STATE_KEY, &ArenaState::Cancelled);")

# Wait, the `is_cancelled` replacement removed one. Let's see if the code compiles after this.
# Also fix init_with_fee to set is_private: false
content = content.replace("                win_fee_bps,\n            },", "                win_fee_bps,\n                is_private: false,\n            },")

with open(f, "w") as file:
    file.write(content)
