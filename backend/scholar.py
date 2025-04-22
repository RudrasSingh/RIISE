from scholarly import scholarly
import json

def get_full_scholar_profile(scholar_id):
    # Search and fill complete author data
    author = scholarly.search_author_id(scholar_id)
    filled_author = scholarly.fill(author, sections=["basics", "indices", "counts", "publications"])

    # Deep-fill each publication (this may take time!)
    publications = []
    for pub in filled_author.get("publications", []):
        pub_filled = scholarly.fill(pub)
        publications.append(pub_filled)

    # Replace shallow publications with deep-filled ones
    filled_author["publications"] = publications

    # Return full JSON
    return filled_author

# Example usage:
if __name__ == "__main__":
    scholar_id = "1UE6AW8AAAAJ"  # Replace with any valid scholar ID
    full_profile = get_full_scholar_profile(scholar_id)

    # Print pretty JSON
    print(json.dumps(full_profile, indent=2))
