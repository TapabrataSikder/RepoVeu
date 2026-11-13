from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

# for one piece of text
def generate_embedding(text):
    return model.encode(text)

# for multiple chunks
def generate_embeddings(texts):
    return model.encode(texts)

if __name__ == "__main__":
    text = """
    public void login(String username) {
        authenticate(username);
    }
    """

    embedding = generate_embedding(text)

    print("Embedding generated successfully")
    print(f"Vector dimensions: {len(embedding)}")
    print(f"First 10 values: {embedding[:10]}")