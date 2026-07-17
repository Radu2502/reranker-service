from sentence_transformers import CrossEncoder

model = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")

query = "Cum resetez parola?"
docs = [
    "Pentru a reseta parola, mergi la Setări și apasă pe „Schimbă parola”.",
    "Programul bibliotecii este între orele 9 și 17.",
    "Ai uitat parola? Folosește linkul de recuperare din pagina de autentificare.",
]

pairs = [(query, d) for d in docs]
scores = model.predict(pairs)

for doc, score in zip(docs, scores):
    print(round(float(score), 3), "->", doc)