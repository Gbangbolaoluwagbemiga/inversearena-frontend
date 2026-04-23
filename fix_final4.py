import re

# 1. fix state_machine_tests.rs double init
f = "contract/arena/src/state_machine_tests.rs"
with open(f, "r") as file:
    content = file.read()
content = content.replace("    client.init(&5, &100, &3600);\n", "")
with open(f, "w") as file:
    file.write(content)

# 2. fix commit_reveal_tests.rs
f = "contract/arena/src/commit_reveal_tests.rs"
with open(f, "r") as file:
    content = file.read()
# Replace `round_deadline_ledger + 1` with `round_deadline_ledger` everywhere EXCEPT in `test_reveal_after_deadline`
# Actually, wait. The test `test_reveal_after_deadline` EXPECTS `reveal_after_deadline` to panic!
# So we should leave `round_deadline_ledger + 1` in `test_reveal_after_deadline` and `test_commit_after_deadline`
# Let's do it test by test.

# test_happy_path
content = re.sub(
    r"(fn test_happy_path.*?set_ledger_sequence\(&env, round\.round_deadline_ledger) \+ 1(;\n.*?client\.reveal_choice)",
    r"\1\2",
    content, flags=re.DOTALL
)

# test_reveal_without_commit
# This test expects Error 37. Wait, if we change the ledger to `round_deadline_ledger`, it will NOT panic with Error 5, but will it panic with Error 37?
# No, `reveal_choice` does NOT check commitment! It will just SUCCEED!
# So if it succeeds, the `should_panic` test will fail!
# Because the implementation doesn't check it. We MUST implement the check in `reveal_choice`!

