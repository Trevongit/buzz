use super::{known_acp_runtime, known_acp_runtime_exact, normalize_agent_args};

#[test]
fn antigravity_runtime_registers_agy_acp_adapter() {
    let runtime = known_acp_runtime_exact("antigravity").expect("antigravity runtime");
    assert_eq!(runtime.commands, &["agy-acp"]);
    assert_eq!(runtime.underlying_cli, Some("agy"));
    assert_eq!(runtime.aliases, &["agy"]);
    assert!(
        known_acp_runtime("agy-acp").is_some(),
        "agy-acp command should resolve to antigravity"
    );
    assert_eq!(
        normalize_agent_args("agy-acp", vec!["acp".into()]),
        Vec::<String>::new()
    );
}
