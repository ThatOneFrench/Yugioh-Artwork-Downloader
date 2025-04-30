import os
import sys
import time
import json
import logging
import requests
from typing import List, Dict, Optional, Any
from pathlib import Path
import shutil
from dataclasses import dataclass
import argparse
from github import Github
from github.Repository import Repository
from github.ContentFile import ContentFile


@dataclass
class CardImage:
    id: int
    image_url: str
    image_url_small: str
    image_url_cropped: str


@dataclass
class Card:
    id: int
    name: str
    card_images: List[CardImage]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Card':
        """Create a Card instance from API data dictionary."""
        card_images = [
            CardImage(
                id=img["id"],
                image_url=img["image_url"],
                image_url_small=img["image_url_small"],
                image_url_cropped=img["image_url_cropped"]
            )
            for img in data.get("card_images", [])
        ]
        
        return cls(
            id=data["id"],
            name=data["name"],
            card_images=card_images
        )


class YuGiOhAPI:
    """Class for interacting with the YGOProDeck API."""
    
    BASE_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    REQUEST_DELAY = 0.05  # 50ms delay between requests to respect rate limiting
    
    def __init__(self):
        self.logger = logging.getLogger("YuGiOhAPI")
    
    def get_all_cards(self) -> List[Card]:
        """Fetch all Yu-Gi-Oh! cards from the API."""
        self.logger.info("Fetching all cards from YGOProDeck API...")
        
        try:
            response = requests.get(self.BASE_URL)
            response.raise_for_status()
            data = response.json()
            
            cards = [Card.from_dict(card_data) for card_data in data.get("data", [])]
            self.logger.info(f"Successfully fetched {len(cards)} cards.")
            return cards
            
        except requests.RequestException as e:
            self.logger.error(f"Error fetching cards: {e}")
            raise
    
    def download_card_image(self, url: str, save_path: Path) -> bool:
        """Download card image from URL and save it to the specified path."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
                
            self.logger.debug(f"Downloaded image: {save_path}")
            time.sleep(self.REQUEST_DELAY)  # Respect rate limiting
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Error downloading image {url}: {e}")
            return False


class GitHubRepository:
    """Class for interacting with GitHub repositories."""
    
    def __init__(self, token: str, repo_name: str):
        self.logger = logging.getLogger("GitHubRepository")
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_name)
        self.logger.info(f"Connected to GitHub repository: {repo_name}")
    
    def upload_file(self, file_path: Path, github_path: str) -> bool:
        """Upload a file to the GitHub repository."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
            # Check if file already exists
            try:
                contents = self.repo.get_contents(github_path)
                # If file exists, update it
                self.repo.update_file(
                    github_path,
                    f"Update {github_path}",
                    content,
                    contents.sha
                )
                self.logger.info(f"Updated file: {github_path}")
            except Exception:
                # If file doesn't exist, create it
                self.repo.create_file(
                    github_path,
                    f"Add {github_path}",
                    content
                )
                self.logger.info(f"Created file: {github_path}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error uploading file {github_path}: {e}")
            return False
    
    def get_existing_files(self, directory_path: str) -> List[str]:
        """Get a list of files in the specified directory."""
        try:
            contents = self.repo.get_contents(directory_path)
            if not isinstance(contents, list):
                contents = [contents]
                
            return [content.path for content in contents if not content.type == "dir"]
            
        except Exception as e:
            self.logger.error(f"Error getting files from {directory_path}: {e}")
            return []
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the GitHub repository."""
        try:
            contents = self.repo.get_contents(file_path)
            self.repo.delete_file(
                file_path,
                f"Remove {file_path}",
                contents.sha
            )
            self.logger.info(f"Deleted file: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting file {file_path}: {e}")
            return False


class YuGiOhCardSynchronizer:
    """Main class for synchronizing Yu-Gi-Oh! card images with GitHub repository."""
    
    def __init__(self, github_token: str, repo_name: str, image_dir: str = "images"):
        self.logger = logging.getLogger("YuGiOhCardSynchronizer")
        self.api = YuGiOhAPI()
        self.github_repo = GitHubRepository(github_token, repo_name)
        self.image_dir = image_dir
        self.local_dir = Path("temp_images")
        
        # Create temp directory if it doesn't exist
        if not self.local_dir.exists():
            self.local_dir.mkdir(parents=True)
    
    def clean_up(self):
        """Remove temporary files."""
        if self.local_dir.exists():
            shutil.rmtree(self.local_dir)
            self.logger.info("Cleaned up temporary files.")
    
    def run(self):
        """Main method to synchronize card images with GitHub repository."""
        try:
            # Get all cards from API
            all_cards = self.api.get_all_cards()
            self.logger.info(f"Fetched {len(all_cards)} cards from API")
            
            # Get existing files in GitHub repository
            existing_files = self.github_repo.get_existing_files(self.image_dir)
            existing_ids = set()
            
            for file_path in existing_files:
                filename = os.path.basename(file_path)
                if filename.endswith(".jpg") and filename.split(".")[0].isdigit():
                    existing_ids.add(int(filename.split(".")[0]))
            
            self.logger.info(f"Found {len(existing_ids)} existing card images in the repository")
            
            # Download and upload new card images
            valid_card_ids = set()
            cards_processed = 0
            
            for card in all_cards:
                if not card.card_images:
                    continue
                    
                cards_processed += 1
                if cards_processed % 100 == 0:
                    self.logger.info(f"Processed {cards_processed}/{len(all_cards)} cards")
                
                for image in card.card_images:
                    valid_card_ids.add(image.id)
                    
                    # Skip if image already exists in repository
                    if image.id in existing_ids:
                        continue
                    
                    # Skip if no cropped image available
                    if not image.image_url_cropped:
                        continue
                    
                    # Download image
                    image_path = self.local_dir / f"{image.id}.jpg"
                    if self.api.download_card_image(image.image_url_cropped, image_path):
                        # Upload image to GitHub
                        github_path = f"{self.image_dir}/{image.id}.jpg"
                        self.github_repo.upload_file(image_path, github_path)
            
            # Remove obsolete images
            for file_path in existing_files:
                filename = os.path.basename(file_path)
                if filename.endswith(".jpg") and filename.split(".")[0].isdigit():
                    card_id = int(filename.split(".")[0])
                    if card_id not in valid_card_ids:
                        self.logger.info(f"Removing obsolete image: {file_path}")
                        self.github_repo.delete_file(file_path)
            
            self.logger.info("Card synchronization completed successfully")
            
        finally:
            self.clean_up()


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Yu-Gi-Oh! Card Image Downloader GitHub Action")
    parser.add_argument("--token", required=True, help="GitHub access token")
    parser.add_argument("--repo", required=True, help="GitHub repository name (format: owner/repo)")
    parser.add_argument("--image-dir", default="images", help="Directory in the repository for images")
    
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger("main")
    
    try:
        synchronizer = YuGiOhCardSynchronizer(
            github_token=args.token,
            repo_name=args.repo,
            image_dir=args.image_dir
        )
        synchronizer.run()
        
    except Exception as e:
        logger.error(f"Error running synchronizer: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()