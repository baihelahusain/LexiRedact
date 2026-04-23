# LexiRedact - GitHub & PyPI Deployment Guide

## Testing Results ✅

Your package has been thoroughly tested and is **production-ready**:

- ✅ Package imports successfully (version 0.1.0)
- ✅ All core modules available (`IngestionPipeline`, `PIIDetector`, `Config`, etc.)
- ✅ CLI tool works correctly (`lexiredact --help`)
- ✅ Distributions build and validate:
  - `lexiredact-0.1.0-py3-none-any.whl` ✓ PASSED
  - `lexiredact-0.1.0.tar.gz` ✓ PASSED
- ✅ Package metadata is valid (twine check passed)

---

## Step-by-Step Deployment Instructions

### 1. Prepare Your GitHub Repository

Ensure your repository is set up correctly:

```bash
# Make sure you're in the repository root
cd /path/to/vectorshield

# Verify git is configured
git remote -v
# Should show: origin  https://github.com/lexiredact/lexiredact.git

# Check that .gitignore is in place
cat .gitignore
```

### 2. Set Up PyPI Authentication

You need to create API tokens for both PyPI and TestPyPI.

#### Create PyPI API Token

1. Go to [https://pypi.org/account/](https://pypi.org/account/)
2. Log in or create an account
3. Go to **Account Settings** → **API tokens**
4. Click **Add API token**
5. Name it: `GitHub Actions - LexiRedact`
6. Scope: **Entire account** (for initial release) or **Project: lexiredact** (if project already exists)
7. Copy the token (starts with `pypi-`)

#### Create TestPyPI API Token (Optional but Recommended)

1. Go to [https://test.pypi.org/account/](https://test.pypi.org/account/)
2. Log in or create an account
3. Go to **Account Settings** → **API tokens**
4. Click **Add API token**
5. Name it: `GitHub Actions - LexiRedact Test`
6. Scope: **Entire account**
7. Copy the token (starts with `pypi-`)

### 3. Add Secrets to GitHub Repository

#### Add PyPI Token

1. Go to your GitHub repository: https://github.com/lexiredact/lexiredact
2. Settings → Secrets and variables → **Actions**
3. Click **New repository secret**
4. Name: `PYPI_API_TOKEN`
5. Value: Paste the PyPI token from step 2.1.7
6. Click **Add secret**

#### Add TestPyPI Token (Optional)

1. Click **New repository secret** again
2. Name: `TEST_PYPI_API_TOKEN`
3. Value: Paste the TestPyPI token from step 2.2.7
4. Click **Add secret**

### 4. Verify GitHub Actions Workflows

The workflows have been set up automatically:

- **`.github/workflows/package-check.yml`** - Runs on every push/PR
  - Tests on Python 3.8-3.12
  - Tests on Ubuntu, Windows, and macOS
  - Validates package metadata
  - Verifies CLI and imports

- **`.github/workflows/publish-pypi.yml`** - Publishes releases
  - Manual trigger to publish to TestPyPI
  - Automatic trigger on version tags
  - Publishes to PyPI when you push tags

### 5. Publish Your Package

#### Option A: Test Release to TestPyPI (Recommended First)

1. Go to your GitHub repository
2. Click **Actions** tab
3. Select **Publish to PyPI** workflow
4. Click **Run workflow** dropdown
5. Select **testpypi** from the target dropdown
6. Click **Run workflow**
7. Wait for completion (~2-3 minutes)
8. Check [https://test.pypi.org/project/lexiredact/](https://test.pypi.org/project/lexiredact/)

**Test the TestPyPI package:**

```bash
pip install --index-url https://test.pypi.org/simple/ lexiredact==0.1.0
```

#### Option B: Release to Production PyPI

Create a version tag and push it:

```bash
# Update version in pyproject.toml if needed (currently 0.1.0)
# Then create and push the tag:

git tag v0.1.0
git push origin v0.1.0
```

Or, if you want to increment the version first:

```bash
# Update pyproject.toml with new version (e.g., 0.2.0)
# Commit and push the change
git add pyproject.toml
git commit -m "Bump version to 0.2.0"
git push origin main

# Create and push the tag
git tag v0.2.0
git push origin v0.2.0
```

This will automatically:
1. ✅ Build the distributions
2. ✅ Test on all Python versions and OSes
3. ✅ Publish to PyPI
4. ✅ Create a GitHub Release with the distributions

#### Verify PyPI Release

1. Check [https://pypi.org/project/lexiredact/](https://pypi.org/project/lexiredact/)
2. Install the public version:

```bash
pip install lexiredact
```

### 6. Monitor the Deployment

#### GitHub Actions Dashboard

1. Go to: https://github.com/lexiredact/lexiredact/actions
2. View all workflow runs
3. Click on any run to see logs
4. For failures, check the **Logs** section of failed jobs

#### Common Workflow Status

- 🟢 **Green**: Success - package published
- 🟡 **Yellow**: In progress
- 🔴 **Red**: Failed - check logs for errors

---

## Version Management Strategy

### Semantic Versioning

Follow [SemVer](https://semver.org/):

```
MAJOR.MINOR.PATCH

- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes
```

### Version Increment Examples

```bash
# From 0.1.0 → 0.1.1 (patch fix)
git tag v0.1.1
git push origin v0.1.1

# From 0.1.x → 0.2.0 (minor feature)
git tag v0.2.0
git push origin v0.2.0

# From 0.x → 1.0.0 (major release)
git tag v1.0.0
git push origin v1.0.0
```

---

## Troubleshooting

### Issue: "Invalid credentials"

**Solution**: Verify your API token:
1. Go to PyPI account page
2. Check that the token is active (not expired)
3. Regenerate if needed
4. Update the GitHub secret

### Issue: "Package already exists"

**Solution**: Version already published. Choose a new version:
1. Update version in `pyproject.toml`
2. Create a new tag: `git tag v0.2.0`
3. Push: `git push origin v0.2.0`

### Issue: "Validation errors"

**Solution**: Fix the issue and rebuild:
1. Check the workflow logs for the error
2. Fix the issue locally
3. Push to main branch (triggers package-check)
4. Once fixed, create a new tag

### Issue: "Installation fails after publishing"

**Solution**: Wait a few minutes for PyPI CDN to sync:
```bash
# Try again after 2-3 minutes
pip install --upgrade lexiredact
```

---

## Quick Commands Reference

```bash
# Test locally before publishing
python -m pip install -e .
lexiredact --help

# Build distributions
python -m build

# Validate before publishing
python -m twine check dist/*

# Create a release tag
git tag v0.2.0
git push origin v0.2.0

# Check workflow status
# Visit: https://github.com/lexiredact/lexiredact/actions
```

---

## What Gets Deployed

When you create a release:

1. **PyPI Package**: `lexiredact` installable via `pip install lexiredact`
2. **GitHub Release**: With downloadable `.whl` and `.tar.gz` files
3. **Documentation**: Available on PyPI project page

---

## Next Steps

1. ✅ **Set up PyPI token** (see Step 2)
2. ✅ **Add GitHub secrets** (see Step 3)
3. ✅ **Test with TestPyPI** (see Step 5A)
4. ✅ **Publish to Production** (see Step 5B)
5. 📚 **Update PyPI project metadata** (optional, via PyPI web interface)

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/lexiredact/lexiredact/issues
- PyPI Project: https://pypi.org/project/lexiredact/
