import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.matching.engine import resolve_identity
from core.schemas.person import Person
from core.normalization.names import name_normalize

def test_phase3():
    print("Testing matching engine...")
    
    # Existing person in DB
    existing_person = Person(
        id=1,
        full_name="John Doe",
        normalized_name=name_normalize("John Doe"),
        dob="1990-01-01",
        nationality="USA",
        family_id=1
    )
    
    # New extracted person (e.g., from a passport, slight variation in name)
    new_person = Person(
        full_name="Doe, John",
        normalized_name=name_normalize("Doe, John"),
        dob="1990-01-01",
        nationality="USA"
    )
    
    result = resolve_identity(new_person, [existing_person])
    print(f"Match status: {result.status}")
    print(f"Score: {result.score:.2f}")
    print(f"Matched ID: {result.matched_person_id}")
    print(f"Breakdown: {result.breakdown}")
    
    if result.status == "AUTO_MERGED":
        print("Gate passed: Same person automatically merged.")
    else:
        print("Gate failed: Did not auto-merge.")

if __name__ == "__main__":
    test_phase3()
