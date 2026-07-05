# backend/schema.py

DATABASE_SCHEMA = {
    "drug_molecule": {
        "id_prefix": "M-",
        "id_column_name": "Molecule_ID",
        "expected_headers": [
            "S.No.",
            "Molecule_ID",
            "Molecule_Name",
            "Pharmacological_Class",
            "Indications",
            "Side_Effects",
            "Contraindications"
        ]
    },
    "medicinal_product": {
        "id_prefix": "PROD-",
        "id_column_name": "Product_ID",
        # ⚡ Added Molecule_ID at the end of the strict contract array layout!
        "expected_headers": [
            "S.No.",
            "Product_ID",
            "Brand_Name",
            "Variant_Name",
            "Molecule(s)",
            "Strength(s)",
            "Dosage_Form",
            "Manufacturer_Name",
            "Molecule_ID"
        ]
    }
}

def validate_sheet_schema(sheet_name, current_headers):
    if sheet_name not in DATABASE_SCHEMA:
        return False
    expected = DATABASE_SCHEMA[sheet_name]["expected_headers"]
    return current_headers[:len(expected)] == expected