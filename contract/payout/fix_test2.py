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
content = content.replace("let (_env, admin, client) = setup();", "let (_env, admin, client, _, _factory_client) = setup();")
content = content.replace("let (_env, _admin, client) = setup();", "let (_env, _admin, client, _, _factory_client) = setup();")
content = content.replace("let (env, _admin, client, token_id, _treasury) = setup_with_token();", "let (env, _admin, client, token_id, _treasury, _, factory_client) = setup_with_token();")
content = content.replace("let (env, _admin, client, token_id, treasury) = setup_with_token();", "let (env, _admin, client, token_id, treasury, _, factory_client) = setup_with_token();")

# We have exactly this pattern:
# client.distribute_winnings(&ctx, &pool_id, &round_id, &winner, &amount, &currency);
# client.try_distribute_winnings(&ctx, &1u32, &1u32, &winner, &1000i128, &currency);
# For the loop:
#         client.distribute_winnings(
#             &ctx,
#             &i,

def replacer(m):
    fn_name = m.group(1) # distribute_winnings or try_distribute_winnings
    args = m.group(2)
    
    # Extract pool_id from the args
    arg_list = [x.strip() for x in args.split(',')]
    pool_id_arg = arg_list[1] # second argument is pool_id (e.g. &pool_id, &1u32, &i)
    
    # strip the '&' to get the actual value or variable
    pool_id_val = pool_id_arg[1:] if pool_id_arg.startswith('&') else pool_id_arg
    
    # generate a block that sets the mock factory and then calls the function
    return f"""{{
        let caller = Address::generate(&env);
        factory_client.set_arena(&({pool_id_val} as u64), &caller);
        client.{fn_name}(&caller, {args})
    }}"""

# First let's handle single-line calls
content = re.sub(r'client\.(distribute_winnings|try_distribute_winnings)\(([^)]+)\)', replacer, content)

# But wait, there's one that is multi-line
# client.distribute_winnings(
#             &ctx,
#             &i,
#             &1u32,
#             &Address::generate(&env),
#             &(100i128 + i as i128),
#             &currency,
#         );
# This is actually caught by ([^)]+) because [^)] matches newlines too!

# Now let's fix the unauthorized test case
# Wait, my replacer will replace `client.try_distribute_winnings` in the new test case if it's there. But I haven't appended it yet.

attack_test = """
#[test]
fn test_unauthorized_caller_attack_scenario() {
    let (env, _admin, client, _, factory_client) = setup();
    let attacker = Address::generate(&env);
    let ctx = symbol_short!("ATTACK");
    let pool_id = 1u32;
    
    let valid_arena = Address::generate(&env);
    factory_client.set_arena(&(pool_id as u64), &valid_arena);
    
    let result = client.try_distribute_winnings(
        &attacker,
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
