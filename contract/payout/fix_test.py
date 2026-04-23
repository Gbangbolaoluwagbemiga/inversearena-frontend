import re

with open("src/test.rs", "r") as f:
    content = f.read()

mock_factory = """
#[contract]
pub struct MockFactoryContract;
#[contractimpl]
impl MockFactoryContract {
    pub fn set_arena(env: Env, arena_id: u64, contract: Address) {
        let r = ArenaRef {
            contract,
            status: ArenaStatus::Active,
            host: Address::generate(&env),
        };
        env.storage().instance().set(&arena_id, &r);
    }
    pub fn get_arena_ref(env: Env, arena_id: u64) -> ArenaRef {
        env.storage().instance().get(&arena_id).unwrap()
    }
}
"""

content = re.sub(r'(const TIMELOCK: u64 = 48 \* 60 \* 60;)', mock_factory + r'\n\1', content)

setup_replacement = """fn setup() -> (Env, Address, PayoutContractClient<'static>, Address, MockFactoryContractClient<'static>) {
    let env = Env::default();
    env.mock_all_auths();

    let admin = Address::generate(&env);
    let contract_id = env.register(PayoutContract, (&admin,));

    let factory_id = env.register(MockFactoryContract, ());
    let env_static: &'static Env = unsafe { &*(&env as *const Env) };
    let client = PayoutContractClient::new(env_static, &contract_id);
    let factory_client = MockFactoryContractClient::new(env_static, &factory_id);

    client.init_factory(&factory_id, &admin);

    (env, admin, client, factory_id, factory_client)
}

fn setup_with_token() -> (
    Env,
    Address,
    PayoutContractClient<'static>,
    Address,
    Address,
    Address,
    MockFactoryContractClient<'static>
) {
    let (env, admin, client, factory_id, factory_client) = setup();

    let treasury = Address::generate(&env);
    client.set_treasury(&treasury);

    let token_admin = Address::generate(&env);
    let token_id = env
        .register_stellar_asset_contract_v2(token_admin.clone())
        .address();
    let asset = StellarAssetClient::new(&env, &token_id);
    asset.mint(&client.address, &10_000i128);

    (env, admin, client, token_id, treasury, factory_id, factory_client)
}"""

content = re.sub(r'fn setup\(\) -> \(Env, Address, PayoutContractClient<\'static>\) \{.*?\n}', '', content, flags=re.DOTALL)
content = re.sub(r'fn setup_with_token\(\) -> \(\n.*?\) \{.*?\n}', setup_replacement, content, flags=re.DOTALL)

content = content.replace("let (env, _admin, client) = setup();", "let (env, _admin, client, _, factory_client) = setup();")
content = content.replace("let (_env, admin, client) = setup();", "let (_env, admin, client, _, _) = setup();")
content = content.replace("let (_env, _admin, client) = setup();", "let (_env, _admin, client, _, _) = setup();")
content = content.replace("let (env, _admin, client, token_id, _treasury) = setup_with_token();", "let (env, _admin, client, token_id, _treasury, _, factory_client) = setup_with_token();")
content = content.replace("let (env, _admin, client, token_id, treasury) = setup_with_token();", "let (env, _admin, client, token_id, treasury, _, factory_client) = setup_with_token();")

content = re.sub(r'client\.distribute_winnings\(&ctx, &pool_id, &round_id, &winner, &amount, &currency\);', 
                 r'let caller = Address::generate(&env);\n    factory_client.set_arena(&(pool_id as u64), &caller);\n    client.distribute_winnings(&caller, &ctx, &pool_id, &round_id, &winner, &amount, &currency);', content)

content = re.sub(r'client\.try_distribute_winnings\(&ctx, &1u32, &1u32, &winner, &1000i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&1u64, &caller);\n        client.try_distribute_winnings(&caller, &ctx, &1u32, &1u32, &winner, &1000i128, &currency)\n    }', content)

content = re.sub(r'client\.try_distribute_winnings\(&ctx, &1u32, &1u32, &winner, &0i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&1u64, &caller);\n        client.try_distribute_winnings(&caller, &ctx, &1u32, &1u32, &winner, &0i128, &currency)\n    }', content)

content = re.sub(r'client\.try_distribute_winnings\(&ctx, &1u32, &1u32, &winner, &-1i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&1u64, &caller);\n        client.try_distribute_winnings(&caller, &ctx, &1u32, &1u32, &winner, &-1i128, &currency)\n    }', content)

content = re.sub(r'client\.distribute_winnings\(&ctx, &7u32, &2u32, &winner, &1000i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&7u64, &caller);\n        client.distribute_winnings(&caller, &ctx, &7u32, &2u32, &winner, &1000i128, &currency);\n    }', content)

content = re.sub(r'client\.try_distribute_winnings\(&ctx, &7u32, &2u32, &winner, &9999i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&7u64, &caller);\n        client.try_distribute_winnings(&caller, &ctx, &7u32, &2u32, &winner, &9999i128, &currency)\n    }', content)

content = re.sub(r'client\.distribute_winnings\(&ctx, &1u32, &1u32, &winner, &1000i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&1u64, &caller);\n        client.distribute_winnings(&caller, &ctx, &1u32, &1u32, &winner, &1000i128, &currency);\n    }', content)

content = re.sub(r'client\.distribute_winnings\(&ctx, &1u32, &2u32, &winner, &2000i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&1u64, &caller);\n        client.distribute_winnings(&caller, &ctx, &1u32, &2u32, &winner, &2000i128, &currency);\n    }', content)

content = re.sub(r'client\.distribute_winnings\(&ctx, &3u32, &1u32, &winner, &750i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&3u64, &caller);\n        client.distribute_winnings(&caller, &ctx, &3u32, &1u32, &winner, &750i128, &currency);\n    }', content)

content = re.sub(r'client\.distribute_winnings\(&ctx, &7u32, &1u32, &winner, &1234i128, &currency\);',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&7u64, &caller);\n        client.distribute_winnings(&caller, &ctx, &7u32, &1u32, &winner, &1234i128, &currency);\n    }', content)

content = re.sub(r'client\.distribute_winnings\(\n\s*&ctx,\n\s*&i,\n\s*&1u32,\n\s*&Address::generate\(&env\),\n\s*&\(100i128 \+ i as i128\),\n\s*&currency,\n\s*\);',
                 r'{\n            let caller = Address::generate(&env);\n            factory_client.set_arena(&(i as u64), &caller);\n            client.distribute_winnings(&caller, &ctx, &i, &1u32, &Address::generate(&env), &(100i128 + i as i128), &currency);\n        }', content)


content = re.sub(r'client\.try_distribute_winnings\(&ctx, &1u32, &1u32, &winner, &100i128, &currency\)',
                 r'{\n        let caller = Address::generate(&env);\n        factory_client.set_arena(&1u64, &caller);\n        client.try_distribute_winnings(&caller, &ctx, &1u32, &1u32, &winner, &100i128, &currency)\n    }', content)


attack_test = """
#[test]
fn test_unauthorized_caller_attack_scenario() {
    // Attack scenario: an admin key is compromised. The attacker adds a fake ArenaContract address
    // to the whitelist, then calls distribute_winnings(attacker_address, payout_contract_balance).
    // Verifying caller against factory registry means the attacker must also compromise the factory, raising the bar significantly.
    let (env, _admin, client, _, factory_client) = setup();
    let attacker = Address::generate(&env);
    let ctx = symbol_short!("ATTACK");
    let pool_id = 1u32;
    
    // Valid arena is registered in the factory
    let valid_arena = Address::generate(&env);
    factory_client.set_arena(&(pool_id as u64), &valid_arena);
    
    // Attacker tries to call distribute_winnings, pretending to be the arena
    let result = client.try_distribute_winnings(
        &attacker, // Attacker calls with their own address
        &ctx,
        &pool_id,
        &1u32,
        &attacker,
        &1000i128,
        &symbol_short!("XLM"),
    );
    
    assert_eq!(result, Err(Ok(PayoutError::UnauthorizedCaller)));
}
"""

content = content + "\n" + attack_test

with open("src/test.rs", "w") as f:
    f.write(content)
