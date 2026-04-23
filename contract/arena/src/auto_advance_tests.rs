//! Unit tests for auto-advance-round — Issue #440.
//!
//! Acceptance criteria:
//! - Round resolves immediately when the last survivor submits
//! - Round does NOT resolve early when any survivor has not yet submitted
//! - Fallback `resolve_round()` still works after deadline for stragglers
//! - `total_submissions` counter resets to 0 at the start of each round
#![cfg(test)]

extern crate std;

use super::*;
use soroban_sdk::{
    testutils::{Address as _, Ledger as _, LedgerInfo},
    token::StellarAssetClient,
    Address, Env,
};

const STAKE: i128 = 100i128;
const ROUND_SPEED: u32 = 10;

// ── helpers ───────────────────────────────────────────────────────────────────

fn set_seq(env: &Env, seq: u32) {
    let ledger = env.ledger().get();
    env.ledger().set(LedgerInfo {
        sequence_number: seq,
        timestamp: 1_700_000_000,
        protocol_version: 22,
        network_id: ledger.network_id,
        base_reserve: ledger.base_reserve,
        min_temp_entry_ttl: u32::MAX / 4,
        min_persistent_entry_ttl: u32::MAX / 4,
        max_entry_ttl: u32::MAX / 4,
    });
}

fn setup_arena(n: u32) -> (Env, ArenaContractClient<'static>, Address, std::vec::Vec<Address>) {
    let env = Env::default();
    env.mock_all_auths();
    set_seq(&env, 100);

    let contract_id = env.register(ArenaContract, ());
    let admin = Address::generate(&env);

    let env_s: &'static Env = unsafe { &*(&env as *const Env) };
    let client = ArenaContractClient::new(env_s, &contract_id);

    client.initialize(&admin);

    let token_admin = Address::generate(&env);
    let token_id = env
        .register_stellar_asset_contract_v2(token_admin.clone())
        .address();
    let asset = StellarAssetClient::new(&env, &token_id);

    client.set_token(&token_id);
    client.init(&ROUND_SPEED, &STAKE);

    let mut players = std::vec::Vec::new();
    for _ in 0..n {
        let p = Address::generate(&env);
        asset.mint(&p, &1_000i128);
        client.join(&p, &STAKE);
        players.push(p);
    }

    (env, client, token_id, players)
}

// ── AC: Round resolves immediately when last survivor submits ─────────────────

#[test]
fn all_survivors_submit_triggers_auto_advance() {
    let (env, client, _token, players) = setup_arena(3);

    set_seq(&env, 200);
    client.start_round();

    // First two submissions — round must still be active.
    set_seq(&env, 205);
    client.submit_choice(&players[0], &1u32, &Choice::Heads);
    client.submit_choice(&players[1], &1u32, &Choice::Heads);

    let round = client.get_round();
    assert!(round.active, "round must still be active after 2 of 3 submissions");
    assert_eq!(round.total_submissions, 2);

    // Third (last) submission — auto-advance must fire.
    client.submit_choice(&players[2], &1u32, &Choice::Tails);

    let round = client.get_round();
    assert!(!round.active, "round must be inactive after all submissions");
    assert!(round.finished, "round must be marked finished after auto-advance");
}

#[test]
fn auto_advance_emits_round_resolved_event() {
    let (env, client, _token, players) = setup_arena(3);

    set_seq(&env, 200);
    client.start_round();

    set_seq(&env, 205);
    client.submit_choice(&players[0], &1u32, &Choice::Heads);
    client.submit_choice(&players[1], &1u32, &Choice::Heads);

    let before = env.events().all().len();
    client.submit_choice(&players[2], &1u32, &Choice::Tails);

    let new_events = env.events().all().len();
    assert!(new_events > before, "auto-advance must emit at least one new event");
}

// ── AC: Round does NOT resolve early when any survivor has not submitted ──────

#[test]
fn partial_submissions_do_not_trigger_auto_advance() {
    let (env, client, _token, players) = setup_arena(4);

    set_seq(&env, 300);
    client.start_round();

    set_seq(&env, 305);
    // 3 of 4 submit — players[3] stays silent.
    client.submit_choice(&players[0], &1u32, &Choice::Heads);
    client.submit_choice(&players[1], &1u32, &Choice::Heads);
    client.submit_choice(&players[2], &1u32, &Choice::Heads);

    let round = client.get_round();
    assert!(round.active, "round must remain active when not all survivors have submitted");
    assert!(!round.finished, "round must not be finished yet");
    assert_eq!(round.total_submissions, 3);
}

#[test]
fn single_missing_submission_prevents_auto_advance() {
    let (env, client, _token, players) = setup_arena(2);

    set_seq(&env, 400);
    client.start_round();

    set_seq(&env, 405);
    // Only one of two players submits.
    client.submit_choice(&players[0], &1u32, &Choice::Heads);

    let round = client.get_round();
    assert!(round.active, "round must still be active with 1 of 2 submissions");
}

// ── AC: Fallback resolve_round() works after deadline for partial submissions ─

#[test]
fn deadline_fallback_resolve_works_for_partial_submissions() {
    let (env, client, _token, players) = setup_arena(4);

    set_seq(&env, 500);
    let round_state = client.start_round();
    // deadline = 500 + 10 = 510

    set_seq(&env, 505);
    // Only 2 of 4 submit — auto-advance does not fire.
    client.submit_choice(&players[0], &1u32, &Choice::Heads);
    client.submit_choice(&players[1], &1u32, &Choice::Heads);

    // Past deadline: fallback resolve must succeed.
    set_seq(&env, round_state.round_deadline_ledger + 1);
    client.resolve_round();

    let round = client.get_round();
    assert!(!round.active, "round must be inactive after deadline resolve");
    assert!(round.finished, "round must be finished after deadline resolve");
    assert!(round.timed_out, "timed_out flag must be set on deadline path");
}

#[test]
fn resolve_round_works_with_zero_submissions() {
    let (env, client, _token, _players) = setup_arena(3);

    set_seq(&env, 600);
    let round_state = client.start_round();

    // No one submits — past deadline, resolve via fallback.
    set_seq(&env, round_state.round_deadline_ledger + 1);
    client.resolve_round();

    let round = client.get_round();
    assert!(round.finished, "round must resolve even with zero submissions");
}

// ── AC: total_submissions resets to 0 at start of each new round ─────────────

#[test]
fn total_submissions_reset_to_zero_on_new_round() {
    let (env, client, _token, players) = setup_arena(4);

    // Round 1: 3 of 4 submit the same choice (no eliminations), resolve via deadline.
    set_seq(&env, 700);
    client.start_round();

    set_seq(&env, 705);
    client.submit_choice(&players[0], &1u32, &Choice::Heads);
    client.submit_choice(&players[1], &1u32, &Choice::Heads);
    client.submit_choice(&players[2], &1u32, &Choice::Heads);
    // players[3] does not submit.

    set_seq(&env, 711);
    client.resolve_round();

    let round1 = client.get_round();
    assert_eq!(round1.total_submissions, 3);

    // Round 2: check counter reset.
    set_seq(&env, 720);
    client.start_round();

    let round2 = client.get_round();
    assert_eq!(round2.total_submissions, 0, "submissions counter must reset to 0 for round 2");
    assert_eq!(round2.round_number, 2, "must be round 2");
}

// ── AC: resolve_round() returns NoActiveRound after auto-advance resolved it ──

#[test]
fn resolve_round_returns_no_active_round_after_auto_advance() {
    // Use a choice setup where no one is eliminated: all submit the same side.
    // heads_count=3, tails_count=0 → Heads side survives, tails eliminated = []
    // → 3 survivors remain → game continues, state stays Active.
    let (env, client, _token, players) = setup_arena(3);

    set_seq(&env, 800);
    client.start_round();

    set_seq(&env, 805);
    // All three submit the same choice → auto-advance fires, no one eliminated.
    client.submit_choice(&players[0], &1u32, &Choice::Heads);
    client.submit_choice(&players[1], &1u32, &Choice::Heads);
    client.submit_choice(&players[2], &1u32, &Choice::Heads);

    let round = client.get_round();
    assert!(round.finished, "round must be finished after auto-advance");
    assert!(!round.active, "round must be inactive after auto-advance");

    // Calling resolve_round() on an already-resolved round must be rejected.
    let result = client.try_resolve_round();
    assert_eq!(
        result,
        Err(Ok(ArenaError::NoActiveRound)),
        "resolve_round must return NoActiveRound after auto-advance already resolved"
    );
}

// ── AC: Next round can start after auto-advance ───────────────────────────────

#[test]
fn start_round_succeeds_after_auto_advance() {
    let (env, client, _token, players) = setup_arena(3);

    set_seq(&env, 900);
    client.start_round();

    set_seq(&env, 905);
    // All submit the same choice — auto-advance fires, all survive.
    client.submit_choice(&players[0], &1u32, &Choice::Heads);
    client.submit_choice(&players[1], &1u32, &Choice::Heads);
    client.submit_choice(&players[2], &1u32, &Choice::Heads);

    // Start the next round without going through timeout_round().
    set_seq(&env, 915);
    let round2 = client.start_round();

    assert_eq!(round2.round_number, 2, "must start round 2 after auto-advance");
    assert!(round2.active, "new round must be active");
    assert_eq!(round2.total_submissions, 0, "submissions reset for round 2");
}
