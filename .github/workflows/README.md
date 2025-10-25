# ThumbsUp CI/CD Pipelines

This directory contains GitHub Actions workflows for automated testing, building, and deployment.

## Workflows

### 1. Backend CI/CD (`backend-ci.yml`)
**Triggers:** Push/PR to backend code
- Tests Python code across multiple versions (3.10, 3.11, 3.12)
- Lints code with flake8
- Tests certificate generation
- Builds and validates Docker images
- Runs docker-compose configuration tests

### 2. Frontend CI/CD (`frontend-ci.yml`)
**Triggers:** Push/PR to frontend code
- Installs dependencies and runs linting
- Type checks with TypeScript
- Builds production bundle
- Uploads build artifacts
- Optional: Deploy previews for PRs
- Optional: Deploy to production on main branch

### 3. Client Distribution (`client-dist-ci.yml`)
**Triggers:** Push/PR to client-dist, version tags (v*.*.*)
- **Linux Build:** Creates .deb package for Debian/Ubuntu
- **Windows Build:** Creates .exe installer with NSIS
- **macOS Build:** Creates standalone app bundle
- **Release:** Automatically creates GitHub releases on version tags

### 4. Integration Tests (`integration-test.yml`)
**Triggers:** Push to main/develop, PRs, daily schedule
- Starts full Docker environment
- Tests mDNS service discovery
- Validates client-server communication
- Runs end-to-end workflows

### 5. Security Scanning (`security-scan.yml`)
**Triggers:** Push to main/develop, PRs, weekly schedule
- Scans for vulnerabilities with Trivy
- Python security analysis with Bandit
- Dependency vulnerability checks with Safety
- Docker image scanning
- Secret detection with TruffleHog

### 6. Dependabot (`../dependabot.yml`)
**Triggers:** Automatic, weekly
- Updates GitHub Actions versions
- Updates npm dependencies (frontend)
- Updates Python dependencies (backend)
- Updates Docker base images

## Usage

### Running Locally

Most workflows can be tested locally using [act](https://github.com/nektos/act):

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash  # Linux

# Test backend CI
act -W .github/workflows/backend-ci.yml

# Test frontend CI
act -W .github/workflows/frontend-ci.yml

# Test specific job
act -W .github/workflows/backend-ci.yml -j test
```

### Creating a Release

1. Update version numbers in relevant files
2. Commit changes
3. Create and push a version tag:
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```
4. The `client-dist-ci.yml` workflow will automatically:
   - Build installers for all platforms
   - Create a GitHub release
   - Upload all artifacts

### Secrets Required

Configure these secrets in your GitHub repository settings:

#### Optional (for Docker Hub)
- `DOCKER_USERNAME`: Docker Hub username
- `DOCKER_PASSWORD`: Docker Hub password or access token

#### Optional (for deployment)
- `NETLIFY_AUTH_TOKEN`: For frontend preview/production deploys
- `NETLIFY_SITE_ID`: Netlify site identifier

### Status Badges

Add these to your main README.md:

```markdown
[![Backend CI](https://github.com/andreas-04/thumbs-up/workflows/Backend%20CI%2FCD/badge.svg)](https://github.com/andreas-04/thumbs-up/actions/workflows/backend-ci.yml)
[![Frontend CI](https://github.com/andreas-04/thumbs-up/workflows/Frontend%20CI%2FCD/badge.svg)](https://github.com/andreas-04/thumbs-up/actions/workflows/frontend-ci.yml)
[![Client Distribution](https://github.com/andreas-04/thumbs-up/workflows/Client%20Distribution%20CI%2FCD/badge.svg)](https://github.com/andreas-04/thumbs-up/actions/workflows/client-dist-ci.yml)
[![Security Scan](https://github.com/andreas-04/thumbs-up/workflows/Security%20Scanning/badge.svg)](https://github.com/andreas-04/thumbs-up/actions/workflows/security-scan.yml)
```

## Customization

### Adding Tests

1. Create test files in your project
2. Update workflow to run tests:
   ```yaml
   - name: Run tests
     run: pytest tests/
   ```

### Changing Triggers

Edit the `on:` section of each workflow:
```yaml
on:
  push:
    branches: [ main, your-branch ]
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight
```

### Platform-Specific Builds

The client distribution workflow supports:
- **Linux:** `runs-on: ubuntu-latest`
- **Windows:** `runs-on: windows-latest`
- **macOS:** `runs-on: macos-latest`

### Deployment Targets

Uncomment deployment steps in workflows to enable:
- Netlify/Vercel for frontend
- Docker Hub/GHCR for containers
- AWS S3/CloudFront for static assets

## Troubleshooting

### Workflow Not Running
- Check if the file paths in `on.push.paths` match your changes
- Verify branch names in triggers
- Check GitHub Actions permissions in repository settings

### Build Failures
- Review the workflow logs in the Actions tab
- Test the build locally first
- Check if all secrets are configured

### Artifact Upload Issues
- Ensure the path exists before upload
- Check artifact retention settings
- Verify storage limits haven't been exceeded

## Best Practices

1. **Keep workflows focused:** Each workflow should have a single responsibility
2. **Use caching:** Speed up builds with dependency caching
3. **Fail fast:** Use `continue-on-error: false` for critical steps
4. **Secure secrets:** Never commit secrets, use GitHub Secrets
5. **Test locally:** Use `act` to test workflows before pushing
6. **Monitor costs:** GitHub Actions has usage limits on free tier

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Act - Local Testing](https://github.com/nektos/act)
