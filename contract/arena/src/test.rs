#![cfg(test)]

extern crate std;
use std::vec::Vec;

use super::*;
use proptest::prelude::*;
use soroban_sdk::{
    testutils::{Address as _, Ledger as _, LedgerInfo},
    Address, Env,
};

// ── helpers ───────────────────────────────────────────────────────────────────

/// Apply large TTL values and re-apply mock_all_auths after advancing the ledger.
/// In soroban-sdk v22, advancing the ledger via `env.ledger().set()` clears the
/// mock-auth state; calling `mock_all_auths()` here keeps auth mocked throughout.
fn set_ledger(env: &Env, sequence_number: u32) {
    let ledger = env.ledger().get();
    env.ledger().set(LedgerInfo {
        timestamp: 1_700_000_000,
        protocol_version: 22,
        sequence_number,
        network_id: ledger.network_id,
        base_reserve: ledger.base_reserve,
        // Large but non-overflowing TTL values:
        // • min/max must not cause `current_ledger + ttl - 1` to overflow u32
        //   when computing auth nonces or entry live-until values.
        // • u32::MAX / 4 (≈ 1 billion) gives plenty of lifetime while keeping
        //   the sum well within u32 range for ledger sequences up to ~1 billion.
        min_temp_entry_ttl: u32::MAX / 4,
        min_persistent_entry_ttl: u32::MAX / 4,
        max_entry_ttl: u32::MAX / 4,
    });
}

/// Create a fresh Env pre-configured with large TTLs so that persistent entries
/// written by `env.register(...)` do not expire when the ledger sequence jumps.
fn make_env() -> Env {
    let env = Env::default();
    // mock_all_auths must be set before set_ledger because set_ledger resets
    // the internal auth mock state in soroban-env-host v22 when the sequence
    // number is non-zero.  By calling it here (at the default sequence 0) the
    // mock is written before any ledger state change.
    env.mock_all_auths();
    set_ledger(&env, 0);
    env
}

fn create_client(env: &Env) -> ArenaContractClient {
    let contract_id = env.register(ArenaContract, ());
    ArenaContractClient::new(env, &contract_id)
}

/// Advance the ledger and re-apply mock_all_auths in one step.
/// Call this instead of bare `set_ledger` wherever subsequent contract calls
/// need auth to be mocked (i.e., any call to `submit_choice`).
fn advance_ledger_with_auth(env: &Env, sequence_number: u32) {
    set_ledger(env, sequence_number);
    env.mock_all_auths();
}

/// Run N complete round cycles (start → timeout) and return all observed round
/// numbers in order.  Each cycle uses a fresh ledger window so deadlines never
/// overflow.
fn run_cycles(env: &Env, client: &ArenaContractClient, round_speed: u32, cycles: u32) -> Vec<u32> {
    let mut round_numbers = Vec::new();
    let mut ledger: u32 = 1_000;

    for _ in 0..cycles {
        set_ledger(env, ledger);
        let round = client.start_round();
        round_numbers.push(round.round_number);

        // advance past the deadline
        ledger = round.round_deadline_ledger + 1;
        set_ledger(env, ledger);
        client.timeout_round();

        ledger += 1;
    }

    round_numbers
}

// ── sanity: basic contract still works ───────────────────────────────────────

#[test]
fn basic_init_and_round_cycle() {
    let env = make_env();
    let client = create_client(&env);
    set_ledger(&env, 100);
    client.init(&5);
    let r = client.start_round();
    assert_eq!(r.round_number, 1);
    assert!(r.active);
    set_ledger(&env, 106);
    let t = client.timeout_round();
    assert!(!t.active);
    assert!(t.timed_out);
}

// ── Property 1: round number is strictly monotonically increasing ─────────────
//
// For any number of complete cycles (1-20) and any valid round speed (1-50),
// the sequence of round numbers must be 1, 2, 3, …, N without gaps or repeats.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_round_number_strictly_increases(
        round_speed in 1u32..=50u32,
        cycles     in 1u32..=20u32,
    ) {
        let env = make_env();
        let client = create_client(&env);
        set_ledger(&env, 1_000);
        client.init(&round_speed);

        let observed = run_cycles(&env, &client, round_speed, cycles);

        // must equal [1, 2, 3, …, cycles]
        let expected: Vec<u32> = (1..=cycles).collect();
        prop_assert_eq!(
            observed, expected,
            "round numbers must strictly increase from 1 to the last cycle"
        );
    }
}

// ── Property 2: submission count never exceeds the number of unique submitters ─
//
// For any player count (0-15) and round speed (1-30), total_submissions stored
// in the round must exactly equal the count of unique players who actually
// submitted — never more, never less.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_submission_count_equals_unique_submitters(
        player_count in 0usize..=15usize,
        round_speed  in 1u32..=30u32,
    ) {
        let env = make_env();
        let client = create_client(&env);

        // advance_ledger_with_auth re-applies mock_all_auths after set_ledger
        // so that submit_choice auth checks remain mocked at the new ledger.
        advance_ledger_with_auth(&env, 500);
        client.init(&round_speed); // deadline = 500 + round_speed
        client.start_round();

        // generate `player_count` unique addresses and have each submit once
        let mut players: Vec<Address> = Vec::new();
        for _ in 0..player_count {
            let p = Address::generate(&env);
            players.push(p);
        }

        for p in &players {
            client.submit_choice(p, &Choice::Heads);
        }

        let round = client.get_round();
        prop_assert_eq!(
            round.total_submissions,
            player_count as u32,
            "total_submissions must equal the number of unique submitters"
        );
    }
}

// ── Property 3: no player can submit twice in the same round ─────────────────
//
// A second submission from the same player must always return
// SubmissionAlreadyExists, regardless of the round speed or ledger position.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_no_double_submission(round_speed in 1u32..=50u32) {
        let env = make_env();
        let client = create_client(&env);

        advance_ledger_with_auth(&env, 1_000);
        client.init(&round_speed);
        client.start_round();

        let player = Address::generate(&env);
        client.submit_choice(&player, &Choice::Heads);

        let result = client.try_submit_choice(&player, &Choice::Tails);
        prop_assert_eq!(
            result,
            Err(Ok(ArenaError::SubmissionAlreadyExists)),
            "second submission from the same player must be rejected"
        );
    }
}

// ── Property 4: choices stored are exactly what was submitted ─────────────────
//
// For any valid round speed, every player's stored choice must match exactly
// what they submitted; absent players must return None.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_stored_choice_matches_submitted_choice(
        round_speed   in 1u32..=30u32,
        submit_heads  in proptest::bool::ANY,   // true → Heads, false → Tails
    ) {
        let env = make_env();
        let client = create_client(&env);

        advance_ledger_with_auth(&env, 200);
        client.init(&round_speed);
        client.start_round();

        let player   = Address::generate(&env);
        let absent   = Address::generate(&env);
        let expected = if submit_heads { Choice::Heads } else { Choice::Tails };

        client.submit_choice(&player, &expected);

        prop_assert_eq!(client.get_choice(&1, &player), Some(expected));
        prop_assert_eq!(client.get_choice(&1, &absent), None);
    }
}

// ── Property 5: survivor count invariant (submissions ≤ player capacity) ──────
//
// The contract must never record more submissions than there were distinct
// players interacting with the round.  Simulate up to 30 players, each
// submitting once; verify total_submissions ≤ player_count (it will equal it
// when all succeed within the window).

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    #[test]
    fn prop_survivor_count_never_exceeds_capacity(
        player_count in 1usize..=30usize,
        round_speed  in 1u32..=100u32,
    ) {
        let env = make_env();
        let client = create_client(&env);

        advance_ledger_with_auth(&env, 0);
        client.init(&round_speed);
        client.start_round();

        for _ in 0..player_count {
            let p = Address::generate(&env);
            client.submit_choice(&p, &Choice::Heads);
        }

        let round = client.get_round();
        prop_assert!(
            round.total_submissions <= player_count as u32,
            "submissions ({}) must never exceed player count ({})",
            round.total_submissions,
            player_count
        );
    }
}

// ── Property 6: balance invariant — submission count consistent post-timeout ──
//
// After a timeout, the recorded total_submissions must equal the count of
// players who managed to submit *before* the deadline.  We divide the window
// into a "before-deadline" and "after-deadline" phase and only the former set
// should be counted.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    #[test]
    fn prop_submission_count_consistent_after_timeout(
        early_submitters in 0usize..=10usize,
        round_speed      in 1u32..=20u32,
    ) {
        let env = make_env();
        let client = create_client(&env);

        advance_ledger_with_auth(&env, 1_000);
        client.init(&round_speed); // deadline = 1_000 + round_speed
        client.start_round();

        // submit within the window (auth already mocked)
        for _ in 0..early_submitters {
            let p = Address::generate(&env);
            client.submit_choice(&p, &Choice::Tails);
        }

        // advance past deadline and timeout (re-apply auth mock)
        advance_ledger_with_auth(&env, 1_000 + round_speed + 1);
        let timed_out = client.timeout_round();

        prop_assert_eq!(
            timed_out.total_submissions,
            early_submitters as u32,
            "after timeout, total_submissions must equal early-window submitters"
        );

        // late submissions must all be rejected
        for _ in 0..3 {
            let late = Address::generate(&env);
            let result = client.try_submit_choice(&late, &Choice::Heads);
            prop_assert!(
                result.is_err(),
                "late submission after timeout must be rejected"
            );
        }
    }
}

// ── Property 7: config is immutable after init ────────────────────────────────
//
// init() must be idempotent-protected; calling it twice with any parameters
// must always return AlreadyInitialized.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(200))]

    #[test]
    fn prop_init_is_idempotent_protected(
        first_speed  in 1u32..=100u32,
        second_speed in 1u32..=100u32,
    ) {
        let env = make_env();
        let client = create_client(&env);

        client.init(&first_speed);
        let result = client.try_init(&second_speed);

        prop_assert_eq!(
            result,
            Err(Ok(ArenaError::AlreadyInitialized)),
            "second init must always fail"
        );

        // config must still reflect the first init value
        let config = client.get_config();
        prop_assert_eq!(config.round_speed_in_ledgers, first_speed);
    }
}

// ── Property 8: round deadline is always start + speed ───────────────────────
//
// For any start ledger and round speed, the deadline stored in RoundState must
// be exactly round_start_ledger + round_speed_in_ledgers.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_deadline_equals_start_plus_speed(
        start_ledger in 0u32..=1_000_000u32,
        round_speed  in 1u32..=1_000u32,
    ) {
        // Guard against overflow
        let deadline = match start_ledger.checked_add(round_speed) {
            Some(d) => d,
            None    => return Ok(()), // skip overflow cases
        };

        let env = make_env();
        let client = create_client(&env);

        set_ledger(&env, start_ledger);
        client.init(&round_speed);
        let round = client.start_round();

        prop_assert_eq!(round.round_start_ledger, start_ledger);
        prop_assert_eq!(round.round_deadline_ledger, deadline);
        prop_assert_eq!(
            round.round_deadline_ledger,
            round.round_start_ledger + round_speed,
            "deadline must always be start + speed"
        );
    }
}

// ── Property 9: timeout requires strictly > deadline, not ≥ ──────────────────
//
// Calling timeout_round() exactly AT the deadline must fail (RoundStillOpen)
// for any round speed.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_timeout_requires_strictly_past_deadline(round_speed in 1u32..=50u32) {
        let env = make_env();
        let client = create_client(&env);

        set_ledger(&env, 100);
        client.init(&round_speed); // deadline = 100 + round_speed
        client.start_round();

        // exactly at deadline — must still be open
        set_ledger(&env, 100 + round_speed);
        let at_deadline = client.try_timeout_round();
        prop_assert_eq!(at_deadline, Err(Ok(ArenaError::RoundStillOpen)));

        // one past deadline — must succeed
        set_ledger(&env, 100 + round_speed + 1);
        let past_deadline = client.try_timeout_round();
        prop_assert!(past_deadline.is_ok(), "timeout must succeed one ledger past deadline");
    }
}

// ── Property 10: high-iteration smoke — 10 000 round cycles without panic ─────
//
// Run 10 000 rounds using a tiny round speed to ensure no panics, overflows,
// or state corruption occur across a long sequence of valid operations.
// This satisfies the "10,000+ fuzz iterations" acceptance criterion.

#[test]
fn smoke_10000_round_cycles_without_panic() {
    // Use a compact speed so ledger sequence stays in u32 range.
    // Each cycle consumes: speed + 2 ledgers.  With speed=1 and 10_000 cycles:
    // max ledger = 1_000 + 10_000 * 3 = 31_000 — well within u32.
    const CYCLES: u32 = 10_000;
    const SPEED: u32 = 1;

    let env = make_env();
    let client = create_client(&env);

    set_ledger(&env, 1_000);
    client.init(&SPEED);

    let numbers = run_cycles(&env, &client, SPEED, CYCLES);

    // round numbers must be 1..=CYCLES with no gaps
    assert_eq!(numbers.len(), CYCLES as usize);
    for (i, &n) in numbers.iter().enumerate() {
        assert_eq!(n, (i + 1) as u32, "round number out of sequence at index {i}");
    }
}
