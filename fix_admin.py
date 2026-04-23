import glob, re

# 1. lib.rs
f = "contract/arena/src/lib.rs"
with open(f, "r") as file:
    content = file.read()
# we want to remove the last occurrence of mod abi_guard;
content = "\n".join(["mod abi_guard;" if i == 0 and line == "mod abi_guard;" else ("" if line == "mod abi_guard;" else line) for i, line in enumerate(content.split("\n"))])
# wait, actually let's just find and remove the second one.
lines = []
found = False
for line in content.split("\n"):
    if line == "mod abi_guard;":
        if not found:
            lines.append(line)
            found = True
        else:
            pass # drop the second one
    else:
        lines.append(line)
with open(f, "w") as file:
    file.write("\n".join(lines))

# 2. fixing `let contract_id ...` and `let admin ...` order
for f in glob.glob("contract/arena/src/**/*.rs", recursive=True):
    with open(f, "r") as file:
        content = file.read()
    
    # We will search for:
    # let contract_id = env.register(ArenaContract, (&admin,));
    # let client = ArenaContractClient::new(&env, &contract_id);
    # let admin = Address::generate(&env);
    
    # And replace with:
    # let admin = Address::generate(&env);
    # let contract_id = env.register(ArenaContract, (&admin,));
    # let client = ArenaContractClient::new(&env, &contract_id);
    
    content = re.sub(
        r"let contract_id = env\.register\(ArenaContract, \(&admin,\)\);\n\s*let client = ArenaContractClient::new\(&env, &contract_id\);\n\s*let admin = Address::generate\(&env\);",
        r"let admin = Address::generate(&env);\n    let contract_id = env.register(ArenaContract, (&admin,));\n    let client = ArenaContractClient::new(&env, &contract_id);",
        content
    )
    
    content = re.sub(
        r"let contract_id = env\.register\(ArenaContract, \(&admin,\)\);\n\s*let admin = Address::generate\(&env\);",
        r"let admin = Address::generate(&env);\n    let contract_id = env.register(ArenaContract, (&admin,));",
        content
    )

    # test.rs around line 1061:
    content = re.sub(
        r"let contract_id = env\.register\(ArenaContract, \(&admin,\)\);\n\s*env\.as_contract",
        r"let admin = Address::generate(&env);\n    let contract_id = env.register(ArenaContract, (&admin,));\n    env.as_contract",
        content
    )

    # Let's just fix any env.register before let admin
    pattern = r"let contract_id = env\.register\(ArenaContract, \(&admin,\)\);\n(?:.*?)\n\s*let admin = Address::generate\(&env\);"
    matches = re.findall(r"let contract_id = env\.register\(ArenaContract, \(&admin,\)\);\n(.*?\n)?\s*let admin = Address::generate\(&env\);", content)
    # The safest way is to just do it manually for the files.

    if "let contract_id = env.register(ArenaContract, (&admin,));" in content and "let admin = Address::generate(&env);" in content:
        # Check if contract_id is declared before admin
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if "let contract_id = env.register(ArenaContract, (&admin,));" in line:
                # look ahead for let admin
                for j in range(i+1, min(i+5, len(lines))):
                    if "let admin = Address::generate(&env);" in lines[j]:
                        lines[j] = ""
                        lines.insert(i, "    let admin = Address::generate(&env);")
                        break
        content = "\n".join(lines)
    
    with open(f, "w") as file:
        file.write(content)

