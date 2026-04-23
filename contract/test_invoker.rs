#![no_std]
use soroban_sdk::{contract, contractimpl, Env, Address};
#[contract]
pub struct TestContract;
#[contractimpl]
impl TestContract {
    pub fn test(env: Env) -> Address {
        env.invoker()
    }
}
