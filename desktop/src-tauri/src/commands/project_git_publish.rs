//! One-way GitHub → Buzz copy, and local-first repository create.
//!
//! Gitea and GitLab treat remotes as *one-way* pull or push mirrors. Their
//! bidirectional mode races and fights two sources of truth. Buzz follows the
//! same lesson: publish heads and tags only (Gitea #18174: `git push --mirror`
//! can delete GitHub `refs/pull/*` on the destination). GitHub stays the
//! advertised clone URL unless the user changes it.

use super::project_git_exec::{
    build_git_auth_config, build_git_clone_auth_config, run_git, validate_github_clone_url,
    validate_workspace_clone_url, GitAuthConfig,
};
use super::project_git_workflow::{clone_destination_root, ProjectRepoCloneResult};
use super::project_repo_paths::{find_local_repo_dir, local_repo_candidates};
use crate::app_state::AppState;
use serde::Serialize;
use tauri::State;

#[derive(Serialize)]
pub struct ProjectRepoPublishResult {
    pub published: bool,
    pub dest_clone_url: String,
    pub message: String,
}

pub(crate) fn publish_repo_copy_blocking(
    source_clone_url: &str,
    dest_clone_url: &str,
    source_auth: &GitAuthConfig,
    dest_auth: &GitAuthConfig,
) -> Result<ProjectRepoPublishResult, String> {
    if source_clone_url.trim_end_matches('/') == dest_clone_url.trim_end_matches('/') {
        return Err("Source and destination remotes must be different.".to_string());
    }
    let temp_dir = tempfile::tempdir().map_err(|error| format!("create temp dir: {error}"))?;
    let mirror_dir = temp_dir.path().join("mirror.git");
    let mirror_path = mirror_dir
        .to_str()
        .ok_or_else(|| "temporary repository path is not UTF-8".to_string())?;
    run_git(
        &[
            "clone",
            "--bare",
            "--end-of-options",
            source_clone_url,
            mirror_path,
        ],
        None,
        source_auth,
    )?;
    // Heads + tags only. Do not push GitHub `refs/pull/*`.
    run_git(
        &[
            "push",
            "--end-of-options",
            dest_clone_url,
            "+refs/heads/*:refs/heads/*",
            "+refs/tags/*:refs/tags/*",
        ],
        Some(&mirror_dir),
        dest_auth,
    )?;
    Ok(ProjectRepoPublishResult {
        published: true,
        dest_clone_url: dest_clone_url.to_string(),
        message: "Published a one-way copy to this relay. GitHub remains the advertised remote."
            .to_string(),
    })
}

fn read_git_identity(auth: &GitAuthConfig) -> (String, String) {
    let read = |key: &str| {
        run_git(&["config", "--get", key], None, auth)
            .ok()
            .map(|output| output.trim().to_string())
            .filter(|value| !value.is_empty())
    };
    (
        read("user.name").unwrap_or_else(|| "Buzz".to_string()),
        read("user.email").unwrap_or_else(|| "buzz@localhost".to_string()),
    )
}

pub(crate) fn init_project_local_repository_blocking(
    repos_dir: Option<&str>,
    project_dtag: &str,
    project_name: &str,
    description: Option<&str>,
    auth: &GitAuthConfig,
) -> Result<ProjectRepoCloneResult, String> {
    if let Some(repo_dir) = find_local_repo_dir(repos_dir, project_dtag, None)? {
        return Ok(ProjectRepoCloneResult {
            path: repo_dir.display().to_string(),
            cloned: false,
            message: "Local repository already exists.".to_string(),
        });
    }

    let repos_root = clone_destination_root(repos_dir)?;
    let repo_name = local_repo_candidates(project_dtag, None)
        .into_iter()
        .next()
        .ok_or_else(|| "Could not derive a directory name for the repository.".to_string())?;
    let repo_dir = repos_root.join(repo_name);
    if repo_dir.exists() {
        return Err(format!(
            "{} already exists but is not a git checkout.",
            repo_dir.display()
        ));
    }
    let repo_path = repo_dir
        .to_str()
        .ok_or_else(|| "repository path is not UTF-8".to_string())?;
    if run_git(
        &[
            "init",
            "--initial-branch=main",
            "--end-of-options",
            repo_path,
        ],
        None,
        auth,
    )
    .is_err()
    {
        run_git(&["init", "--end-of-options", repo_path], None, auth)?;
        run_git(
            &["symbolic-ref", "HEAD", "refs/heads/main"],
            Some(&repo_dir),
            auth,
        )?;
    }

    let readme = match description.map(str::trim).filter(|value| !value.is_empty()) {
        Some(description) => format!("# {project_name}\n\n{description}\n"),
        None => format!("# {project_name}\n"),
    };
    std::fs::write(repo_dir.join("README.md"), readme)
        .map_err(|error| format!("write README.md: {error}"))?;
    run_git(&["add", "--", "README.md"], Some(&repo_dir), auth)?;
    let (name, email) = read_git_identity(auth);
    let name_config = format!("user.name={name}");
    let email_config = format!("user.email={email}");
    run_git(
        &[
            "-c",
            name_config.as_str(),
            "-c",
            email_config.as_str(),
            "commit",
            "-m",
            "Initial commit",
        ],
        Some(&repo_dir),
        auth,
    )?;

    Ok(ProjectRepoCloneResult {
        path: repo_dir.display().to_string(),
        cloned: true,
        message: format!("Created local repository at {}.", repo_dir.display()),
    })
}

#[tauri::command]
pub async fn publish_github_repo_to_buzz(
    github_clone_url: String,
    dest_clone_url: String,
    state: State<'_, AppState>,
) -> Result<ProjectRepoPublishResult, String> {
    validate_github_clone_url(&github_clone_url)?;
    validate_workspace_clone_url(&dest_clone_url, &state)?;
    let source_auth = build_git_clone_auth_config(&github_clone_url, &state)?;
    let dest_auth = build_git_auth_config(&state)?;
    tauri::async_runtime::spawn_blocking(move || {
        publish_repo_copy_blocking(&github_clone_url, &dest_clone_url, &source_auth, &dest_auth)
    })
    .await
    .map_err(|error| format!("publish copy task failed: {error}"))?
}

#[tauri::command]
pub async fn init_project_local_repository(
    repos_dir: Option<String>,
    project_dtag: String,
    project_name: String,
    description: Option<String>,
    state: State<'_, AppState>,
) -> Result<ProjectRepoCloneResult, String> {
    let auth = build_git_auth_config(&state)?;
    tauri::async_runtime::spawn_blocking(move || {
        init_project_local_repository_blocking(
            repos_dir.as_deref(),
            &project_dtag,
            &project_name,
            description.as_deref(),
            &auth,
        )
    })
    .await
    .map_err(|error| format!("local repository init task failed: {error}"))?
}

#[cfg(test)]
mod tests {
    use super::{init_project_local_repository_blocking, publish_repo_copy_blocking};
    use crate::commands::project_git_exec::{build_test_git_auth_config, run_git};
    use crate::commands::project_repo_paths::find_local_repo_dir;

    fn commit_readme(
        repo: &std::path::Path,
        auth: &crate::commands::project_git_exec::GitAuthConfig,
    ) {
        std::fs::write(repo.join("README.md"), "source\n").expect("write");
        run_git(&["add", "README.md"], Some(repo), auth).expect("add");
        run_git(
            &[
                "-c",
                "user.name=Buzz Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                "Initial commit",
            ],
            Some(repo),
            auth,
        )
        .expect("commit");
    }

    #[test]
    fn publish_copy_pushes_heads_not_pull_refs() {
        let auth = build_test_git_auth_config().expect("auth");
        let root = tempfile::tempdir().expect("root");
        let source = root.path().join("source");
        let dest = root.path().join("dest.git");
        let source_path = source.to_str().expect("source path");
        let dest_path = dest.to_str().expect("dest path");

        run_git(
            &["init", "--initial-branch=main", "--", source_path],
            None,
            &auth,
        )
        .or_else(|_| {
            run_git(&["init", "--", source_path], None, &auth)?;
            run_git(
                &["symbolic-ref", "HEAD", "refs/heads/main"],
                Some(&source),
                &auth,
            )
        })
        .expect("init source");
        commit_readme(&source, &auth);
        run_git(
            &["update-ref", "refs/pull/1/head", "HEAD"],
            Some(&source),
            &auth,
        )
        .expect("fake pull ref");
        run_git(&["init", "--bare", "--", dest_path], None, &auth).expect("init dest");

        publish_repo_copy_blocking(source_path, dest_path, &auth, &auth).expect("publish");

        assert!(run_git(
            &[
                format!("--git-dir={dest_path}").as_str(),
                "show-ref",
                "--verify",
                "refs/heads/main",
            ],
            None,
            &auth,
        )
        .is_ok());
        assert!(run_git(
            &[
                format!("--git-dir={dest_path}").as_str(),
                "show-ref",
                "--verify",
                "refs/pull/1/head",
            ],
            None,
            &auth,
        )
        .is_err());
    }

    #[test]
    fn local_first_init_creates_readme_and_is_findable() {
        let auth = build_test_git_auth_config().expect("auth");
        let root = tempfile::tempdir().expect("root");
        let repos = root.path().join("REPOS");
        std::fs::create_dir_all(&repos).expect("repos");
        let repos_dir = repos.to_str().expect("repos path");

        let result = init_project_local_repository_blocking(
            Some(repos_dir),
            "bee-garden-game",
            "Bee Garden",
            Some("A local-first project."),
            &auth,
        )
        .expect("init");

        assert!(result.cloned);
        assert!(std::path::Path::new(&result.path)
            .join("README.md")
            .exists());
        let found = find_local_repo_dir(
            Some(repos_dir),
            "bee-garden-game",
            Some("https://github.com/example/bee-garden-game.git"),
        )
        .expect("find");
        assert_eq!(
            found
                .expect("local-first checkout")
                .canonicalize()
                .expect("canon"),
            std::path::PathBuf::from(&result.path)
                .canonicalize()
                .expect("result canon")
        );
    }
}
