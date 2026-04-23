import re

f = "contract/factory/src/test.rs"
with open(f, "r") as file:
    content = file.read()

# Fix 1: let contract_id = env.register(FactoryContract, ());
# let client = FactoryContractClient::new(&env, &contract_id);
# let admin = Address::generate(&env);
# client.initialize(&admin);
content = re.sub(
    r"let contract_id = env\.register\(FactoryContract, \(\)\);\n\s*let client = FactoryContractClient::new\(&env, &contract_id\);\n\s*let admin = Address::generate\(&env\);\n\s*client\.initialize\(&admin\);",
    r"let admin = Address::generate(&env);\n    let contract_id = env.register(FactoryContract, (&admin,));\n    let client = FactoryContractClient::new(&env, &contract_id);",
    content
)

# Fix 2: catch_unwind
content = content.replace("std::panic::catch_unwind", "std::panic::catch_unwind") # if it wasn't replaced
if "catch_unwind" in content and "use std::panic::catch_unwind;" not in content and "#![no_std]" not in content: # test modules often don't have no_std
    # actually, Soroban test module does have no_std inherited, so we need `extern crate std;`
    if "extern crate std;" not in content:
        content = content.replace("#[cfg(test)]\n", "#[cfg(test)]\nextern crate std;\n")
        content = content.replace("use core::panic::catch_unwind;", "use std::panic::catch_unwind;")

# Ensure all `client.initialize(&admin);` are gone for FactoryContract
content = re.sub(r"client\.initialize\(&admin\);\n", "", content)

# Also fix get_arenas max limit, in case there are other instances
# Let's write the file back
with open(f, "w") as file:
    file.write(content)

