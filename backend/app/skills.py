import re

# canonical skill -> ways it shows up in resumes and job descriptions
SKILLS: dict[str, list[str]] = {
    "JavaScript": ["javascript", "js", "es6"],
    "TypeScript": ["typescript", "ts"],
    "Node.js": ["node.js", "nodejs", "node"],
    "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs"],
    "Angular": ["angular"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "Express": ["express", "express.js", "expressjs"],
    "NestJS": ["nestjs", "nest.js"],
    "Redux": ["redux"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Tailwind CSS": ["tailwind", "tailwindcss"],
    "Python": ["python"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "Java": ["java"],
    "Spring": ["spring", "spring boot"],
    "Go": ["golang", "go"],
    "Rust": ["rust"],
    "C#": ["c#", "csharp"],
    ".NET": [".net", "dotnet", "asp.net"],
    "PHP": ["php"],
    "Laravel": ["laravel"],
    "Ruby": ["ruby"],
    "Rails": ["rails", "ruby on rails"],
    "C++": ["c++"],
    "SQL": ["sql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch"],
    "GraphQL": ["graphql"],
    "REST APIs": ["rest", "restful", "rest api", "rest apis"],
    "Microservices": ["microservices", "microservice"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Terraform": ["terraform"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration"],
    "Git": ["git", "github", "gitlab"],
    "Linux": ["linux"],
    "Jest": ["jest"],
    "Pytest": ["pytest"],
    "Cypress": ["cypress"],
    "Playwright": ["playwright"],
    "Selenium": ["selenium"],
    "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq"],
    "Celery": ["celery"],
    "WebSockets": ["websocket", "websockets", "socket.io"],
    "OAuth": ["oauth", "oauth2"],
    "JWT": ["jwt"],
    "Stripe": ["stripe"],
    "Serverless": ["serverless", "lambda", "aws lambda"],
    "Firebase": ["firebase"],
    "Supabase": ["supabase"],
    "Prisma": ["prisma"],
    "TypeORM": ["typeorm"],
    "SQLAlchemy": ["sqlalchemy"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "LLMs": ["llm", "llms", "large language model", "large language models", "openai", "anthropic", "gpt"],
    "LangChain": ["langchain"],
    "LangGraph": ["langgraph"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented"],
    "Vector Search": ["vector search", "pgvector", "pinecone", "chromadb", "embeddings"],
    "NLP": ["nlp", "natural language processing"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "Airflow": ["airflow"],
    "Spark": ["spark", "pyspark"],
    "Snowflake": ["snowflake"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi"],
    "Figma": ["figma"],
    "Agile": ["agile", "scrum"],
    "Jira": ["jira"],
    "Nginx": ["nginx"],
    "Puppeteer": ["puppeteer"],
    "Razorpay": ["razorpay"],
}

# short aliases that are also ordinary words only count when written the way the technology is written
CASE_SENSITIVE = {"go": "Go", "rest": "REST", "ml": "ML", "ts": "TS", "js": "JS", "spring": "Spring", "rust": "Rust"}
# too common as plain words to extract from free text; still fine when a user types them as a skill
EXTRACT_SKIP = {"express", "lambda"}

_patterns: list[tuple[str, re.Pattern]] = []
for canonical, aliases in SKILLS.items():
    for alias in aliases:
        if alias in EXTRACT_SKIP:
            continue
        # word boundaries do not work around characters like # or +, so use lookarounds
        if alias in CASE_SENSITIVE:
            pattern = r"(?<![\w.+#])" + re.escape(CASE_SENSITIVE[alias]) + r"(?![\w+#])"
            _patterns.append((canonical, re.compile(pattern)))
        else:
            pattern = r"(?<![\w.+#])" + re.escape(alias) + r"(?![\w+#])"
            _patterns.append((canonical, re.compile(pattern, re.IGNORECASE)))


def extract_skills(text: str) -> list[str]:
    found: list[str] = []
    for canonical, pattern in _patterns:
        if canonical not in found and pattern.search(text):
            found.append(canonical)
    return found


def canonical(skill: str) -> str:
    lowered = skill.strip().lower()
    for name, aliases in SKILLS.items():
        if lowered == name.lower() or lowered in aliases:
            return name
    return skill.strip()


def normalize_list(skills: list[str]) -> list[str]:
    out: list[str] = []
    for s in skills:
        c = canonical(s)
        if c and c not in out:
            out.append(c)
    return out
