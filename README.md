# Yu-Gi-Oh! Card Downloader GitHub Action

This GitHub Action automatically downloads Yu-Gi-Oh! card images from the YGOProDeck API and uploads them to your repository.

## Usage

Add this workflow to your GitHub repository by creating a `.github/workflows/download-yugioh-cards.yml` file:

```yaml
name: Download Yu-Gi-Oh! Card Images

on:
  schedule:
    - cron: '0 0 * * 0'  # Run weekly on Sunday at midnight
  workflow_dispatch:  # Allow manual triggering

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Download Yu-Gi-Oh! Card Images
        uses: ThatOneFrench/Yugioh-Artwork-Downloader@main
        with:
          github_token: ${{ secrets.DEPLOY_TOKEN }}
          repository: ${{ github.repository }}
          image_directory: 'images'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `github_token` | GitHub token for repository access | Yes | N/A |
| `repository` | Repository name in the format `owner/repo` | Yes | N/A |
| `image_directory` | Directory in the repository for card images | No | `images` |
