#![no_std]

use soroban_sdk::{
    Address, Env, Symbol, contract, contracterror, contractimpl, contracttype, symbol_short,
    token,
};

// ── Storage keys ──────────────────────────────────────────────────────────────

const ADMIN_KEY: Symbol = symbol_short!("ADMIN");
const PAUSED_KEY: Symbol = symbol_short!("PAUSED");
const TOKEN_KEY: Symbol = symbol_short!("TOKEN");

// ── Event topics ──────────────────────────────────────────────────────────────

const TOPIC_PAUSED: Symbol = symbol_short!("PAUSED");
const TOPIC_UNPAUSED: Symbol = symbol_short!("UNPAUSED");

// ── Error codes ───────────────────────────────────────────────────────────────

#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum StakingError {
    NotInitialized = 1,
    AlreadyInitialized = 2,
    Paused = 3,
    InvalidAmount = 4,
    InsufficientStake = 5,
}

// ── Storage key schema ────────────────────────────────────────────────────────

#[contracttype]
#[derive(Clone)]
enum DataKey {
    Staked(Address),
}

// ── Contract ──────────────────────────────────────────────────────────────────

#[contract]
pub struct StakingContract;

#[contractimpl]
impl StakingContract {
    /// Placeholder function — returns a fixed value for contract liveness checks.
    pub fn hello(_env: Env) -> u32 {
        101112
    }

    // ── Initialisation ───────────────────────────────────────────────────────

    /// Initialise the staking contract. Must be called exactly once after deployment.
    ///
    /// # Arguments
    /// * `env` - The Soroban environment.
    /// * `admin` - Address to designate as the contract administrator.
    /// * `token` - Address of the Soroban token contract used for stake/unstake.
    ///
    /// # Errors
    /// Panics with `"already initialized"` if called more than once.
    ///
    /// # Authorization
    /// None — permissionless; must be called immediately after deploy.
    pub fn initialize(env: Env, admin: Address, token: Address) {
        if env.storage().instance().has(&ADMIN_KEY) {
            panic!("already initialized");
        }
        env.storage().instance().set(&ADMIN_KEY, &admin);
        env.storage().instance().set(&TOKEN_KEY, &token);
    }

    /// Return the current admin address.
    pub fn admin(env: Env) -> Address {
        env.storage()
            .instance()
            .get(&ADMIN_KEY)
            .expect("not initialized")
    }

    // ── Pause mechanism ──────────────────────────────────────────────────────

    /// Pause the contract. Prevents `stake` and `unstake` from executing.
    ///
    /// # Authorization
    /// Requires admin signature.
    pub fn pause(env: Env) {
        let admin = Self::admin(env.clone());
        admin.require_auth();
        env.storage().instance().set(&PAUSED_KEY, &true);
        env.events().publish((TOPIC_PAUSED,), ());
    }

    /// Unpause the contract. Restores normal `stake` and `unstake` operation.
    ///
    /// # Authorization
    /// Requires admin signature.
    pub fn unpause(env: Env) {
        let admin = Self::admin(env.clone());
        admin.require_auth();
        env.storage().instance().set(&PAUSED_KEY, &false);
        env.events().publish((TOPIC_UNPAUSED,), ());
    }

    /// Return whether the contract is currently paused.
    pub fn is_paused(env: Env) -> bool {
        env.storage()
            .instance()
            .get(&PAUSED_KEY)
            .unwrap_or(false)
    }

    // ── Staking ───────────────────────────────────────────────────────────────

    /// Deposit `amount` tokens and record the staked balance for `staker`.
    /// Returns the number of shares minted (1:1 with deposited amount).
    ///
    /// # Arguments
    /// * `env` - The Soroban environment.
    /// * `staker` - Address depositing tokens.
    /// * `amount` - Number of tokens to stake. Must be > 0.
    ///
    /// # Errors
    /// * [`StakingError::Paused`] — Contract is paused.
    /// * [`StakingError::NotInitialized`] — Contract has not been initialized.
    /// * [`StakingError::InvalidAmount`] — `amount` is zero or negative.
    ///
    /// # Authorization
    /// Requires `staker.require_auth()`.
    pub fn stake(env: Env, staker: Address, amount: i128) -> Result<i128, StakingError> {
        require_not_paused(&env)?;
        staker.require_auth();

        if amount <= 0 {
            return Err(StakingError::InvalidAmount);
        }

        let token_contract = get_token_contract(&env)?;
        let token_client = token::Client::new(&env, &token_contract);
        token_client.transfer(&staker, &env.current_contract_address(), &amount);

        let current: i128 = env
            .storage()
            .persistent()
            .get(&DataKey::Staked(staker.clone()))
            .unwrap_or(0);
        env.storage()
            .persistent()
            .set(&DataKey::Staked(staker), &(current + amount));

        Ok(amount)
    }

    /// Withdraw `shares` tokens back to `staker`.
    /// Returns the number of tokens returned (1:1 with shares).
    ///
    /// # Arguments
    /// * `env` - The Soroban environment.
    /// * `staker` - Address withdrawing their stake.
    /// * `shares` - Number of shares to redeem. Must be > 0 and ≤ current staked balance.
    ///
    /// # Errors
    /// * [`StakingError::Paused`] — Contract is paused.
    /// * [`StakingError::NotInitialized`] — Contract has not been initialized.
    /// * [`StakingError::InvalidAmount`] — `shares` is zero or negative.
    /// * [`StakingError::InsufficientStake`] — `shares` exceeds the staker's balance.
    ///
    /// # Authorization
    /// Requires `staker.require_auth()`.
    pub fn unstake(env: Env, staker: Address, shares: i128) -> Result<i128, StakingError> {
        require_not_paused(&env)?;
        staker.require_auth();

        if shares <= 0 {
            return Err(StakingError::InvalidAmount);
        }

        let current: i128 = env
            .storage()
            .persistent()
            .get(&DataKey::Staked(staker.clone()))
            .unwrap_or(0);
        if current < shares {
            return Err(StakingError::InsufficientStake);
        }

        let token_contract = get_token_contract(&env)?;
        let token_client = token::Client::new(&env, &token_contract);
        token_client.transfer(&env.current_contract_address(), &staker, &shares);

        env.storage()
            .persistent()
            .set(&DataKey::Staked(staker), &(current - shares));

        Ok(shares)
    }

    /// Return the staked token balance for `staker`.
    pub fn staked_balance(env: Env, staker: Address) -> i128 {
        env.storage()
            .persistent()
            .get(&DataKey::Staked(staker))
            .unwrap_or(0)
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

fn get_token_contract(env: &Env) -> Result<Address, StakingError> {
    env.storage()
        .instance()
        .get(&TOKEN_KEY)
        .ok_or(StakingError::NotInitialized)
}

fn require_not_paused(env: &Env) -> Result<(), StakingError> {
    if env
        .storage()
        .instance()
        .get(&PAUSED_KEY)
        .unwrap_or(false)
    {
        return Err(StakingError::Paused);
    }
    Ok(())
}

#[cfg(test)]
mod test;

#[cfg(test)]
mod integration_tests;
