from app.ingestion.repository_manifest import (
    create_repository_manifest,
    save_repository_manifest
)


repository_path = (
    "data/repositories/ylzon_python-demo"
)


manifest = create_repository_manifest(
    repository_path=repository_path,
    repository_id="ylzon_python-demo",
    owner="ylzon",
    repository_name="python-demo"
)


print("\n==========================================")
print("REPOSITORY MANIFEST")
print("==========================================")

print(
    "Repository:",
    manifest["repository"]
)

print(
    "Total files:",
    manifest["total_files"]
)

print(
    "Total directories:",
    manifest["total_directories"]
)

print(
    "Languages:",
    manifest["languages"]
)


output_file = save_repository_manifest(
    manifest,
    "data/metadata"
)


print(
    "\nManifest saved:",
    output_file
)