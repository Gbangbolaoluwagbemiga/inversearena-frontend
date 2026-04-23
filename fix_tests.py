import glob, re

# Fix factory/src/test.rs
f = "contract/factory/src/test.rs"
with open(f, "r") as file:
    content = file.read()

# Fix initialize -> __constructor
content = re.sub(
    r"let contract_id = env\.register\(FactoryContract,\s*\(\)\);\s*let c = FactoryContractClient::new\(&env,\s*&contract_id\);\s*c\.initialize\(&admin\);",
    r"let contract_id = env.register(FactoryContract, (&admin,));\n    let c = FactoryContractClient::new(&env, &contract_id);",
    content
)
content = re.sub(
    r"let contract_id = env\.register\(FactoryContract,\s*\(\)\);\s*let admin = Address::generate\(&env\);\s*env\.mock_all_auths\(\);\s*let c = FactoryContractClient::new\(&env,\s*&contract_id\);\s*c\.initialize\(&admin\);",
    r"let admin = Address::generate(&env);\n    let contract_id = env.register(FactoryContract, (&admin,));\n    env.mock_all_auths();\n    let c = FactoryContractClient::new(&env, &contract_id);",
    content
)
# Fix assert_eq!(client.admin(), Ok(admin)) -> assert_eq!(client.admin(), admin)
content = content.replace("assert_eq!(client.admin(), Ok(admin));", "assert_eq!(client.admin(), admin);")

# Fix core::panic::catch_unwind
content = content.replace("core::panic::catch_unwind", "std::panic::catch_unwind")

# Fix execute_upgrade missing arg
content = content.replace("client.execute_upgrade();", "client.execute_upgrade(&soroban_sdk::BytesN::from_array(&env, &[0; 32]));")

with open(f, "w") as file:
    file.write(content)

# Fix arena tests
for f in glob.glob("contract/arena/src/**/*.rs", recursive=True):
    with open(f, "r") as file:
        content = file.read()
    
    # Fix initialize -> __constructor
    content = re.sub(
        r"let contract_id = env\.register\(ArenaContract,\s*\(\)\);\s*let client = ArenaContractClient::new\(&env,\s*&contract_id\);\s*client\.initialize\(&admin\);",
        r"let contract_id = env.register(ArenaContract, (&admin,));\n        let client = ArenaContractClient::new(&env, &contract_id);",
        content
    )
    content = re.sub(
        r"let contract_id = env\.register\(ArenaContract,\s*\(\)\);\s*let admin = Address::generate\(&env\);\s*env\.mock_all_auths\(\);\s*let client = ArenaContractClient::new\(&env,\s*&contract_id\);\s*client\.initialize\(&admin\);",
        r"let admin = Address::generate(&env);\n    let contract_id = env.register(ArenaContract, (&admin,));\n    env.mock_all_auths();\n    let client = ArenaContractClient::new(&env, &contract_id);",
        content
    )
    # Fix try_init(&5, &TEST_REQUIRED_STAKE) -> try_init(&5, &TEST_REQUIRED_STAKE, &3600)
    content = re.sub(r"try_init\(([^,]+),\s*([^,)]+)\)", r"try_init(\1, \2, &3600)", content)
    
    # Fix DataKey::ContractAdmin -> DataKey::Admin
    content = content.replace("DataKey::ContractAdmin", "DataKey::Admin")

    # Fix client.execute_upgrade() missing arg
    content = content.replace("client.execute_upgrade();", "client.execute_upgrade(&soroban_sdk::BytesN::from_array(&env, &[0; 32]));")

    if new_content := content:
        with open(f, "w") as file:
            file.write(new_content)

