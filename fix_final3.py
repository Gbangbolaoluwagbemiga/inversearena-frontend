import re

# 1. fix factory/src/test.rs
f = "contract/factory/src/test.rs"
with open(f, "r") as file:
    content = file.read()
content = content.replace("std::panic::catch_unwind(||", "std::panic::catch_unwind(std::panic::AssertUnwindSafe(||")
content = content.replace("env.register(FactoryContract, (&admin,));\n    });", "env.register(FactoryContract, (&admin,));\n    }));")
with open(f, "w") as file:
    file.write(content)

# 2. fix missing let admin in arena tests
files = [
    "contract/arena/src/mutation_tests.rs",
    "contract/arena/src/state_machine_tests.rs",
    "contract/arena/src/test.rs",
]
for f in files:
    with open(f, "r") as file:
        content = file.read()
    
    # We replace any `let contract_id = env.register(ArenaContract, (&admin,));` 
    # where admin is NOT defined right before it, but actually the simplest is just to add let admin = ... right before
    # Let's just find `let contract_id = env.register` and see if `let admin = Address::generate` is above it.
    
    # Let's find line by line:
    lines = content.split('\n')
    for i in range(len(lines)):
        if "let contract_id = env.register(ArenaContract, (&admin,));" in lines[i]:
            # check previous line
            if "let admin" not in lines[i-1] and "let admin" not in lines[i-2] and "let admin" not in lines[i-3] and "let admin" not in lines[i-4]:
                lines[i] = "    let admin = Address::generate(&env);\n" + lines[i]
    content = "\n".join(lines)
    
    with open(f, "w") as file:
        file.write(content)

