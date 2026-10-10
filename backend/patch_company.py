import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))


def edit(p, old, new, count=1):
    s = open(p, encoding="utf-8").read()
    assert s.count(old) == count, (p, s.count(old), old[:70])
    open(p, "w", encoding="utf-8", newline="\n").write(s.replace(old, new))


# ---- company profile: schema, collection, reset keeps it
open("app/schemas/company.py", "w", encoding="utf-8", newline="\n").write('''"""Our own company identity, editable in the app. Falls back to .env until it is set. Owner: lead."""

from app.schemas.common import ContractModel


class CompanyInput(ContractModel):
    name: str
    name_latin: str
    operator_name: str
    operator_name_latin: str


class CompanyProfile(CompanyInput):
    id: str = "company"  # single record
''')

edit("app/schemas/__init__.py", "from app.schemas.events import DomainEvent\n",
     "from app.schemas.company import CompanyInput, CompanyProfile\nfrom app.schemas.events import DomainEvent\n")
edit("app/schemas/__init__.py", '    "email_insights": (EmailInsight, "email_id"),\n}',
     '    "email_insights": (EmailInsight, "email_id"),\n    "company": (CompanyProfile, "id"),\n}')

edit("app/repository/repo.py", '        self.email_insights: Collection[EmailInsight] = c("email_insights")\n',
     '        self.email_insights: Collection[EmailInsight] = c("email_insights")\n        self.company: Collection[CompanyProfile] = c("company")\n')
edit("app/repository/repo.py", '''    def wipe(self) -> None:
        for name in COLLECTIONS:
            self.collection(name).clear()''', '''    def wipe(self) -> None:
        for name in COLLECTIONS:
            if name not in KEEP_ON_RESET:
                self.collection(name).clear()''')
edit("app/repository/repo.py", "class Repository:\n", 'KEEP_ON_RESET = {"company"}  # user-entered settings survive a demo reset\n\n\nclass Repository:\n')
edit("app/repository/repo.py", "from app.schemas import", "from app.schemas import CompanyProfile,")

open("app/company.py", "w", encoding="utf-8", newline="\n").write('''"""Effective company identity: the saved profile if any, else the .env defaults. Owner: lead."""

from app.core.config import Settings
from app.repository import Repository
from app.schemas import CompanyInput, CompanyProfile


def effective(repo: Repository, settings: Settings) -> CompanyInput:
    saved = repo.company.get("company")
    if saved is not None:
        return CompanyInput(**saved.model_dump(exclude={"id"}))
    return CompanyInput(
        name=settings.company_name,
        name_latin=settings.company_name_latin,
        operator_name=settings.operator_name,
        operator_name_latin=settings.operator_name_latin,
    )


def save(repo: Repository, body: CompanyInput) -> CompanyProfile:
    return repo.company.upsert(CompanyProfile(**body.model_dump()))
''')

# ---- LLM system prompt follows the company name without a restart
edit("app/llm/client.py", "        self.system_prompt = build_system_prompt(settings.company_name, settings.operator_name)\n",
     "        self.system_prompt = build_system_prompt(settings.company_name, settings.operator_name)\n\n"
     "    def set_company(self, name: str, operator: str) -> None:\n"
     "        self.system_prompt = build_system_prompt(name, operator)\n")

# ---- drafts use the effective company; payment reminders can come from a file's facts
svc = "app/drafting/service.py"
edit(svc, "def _context(req: GenerateDraftRequest, repo: Repository) -> tuple[dict, list[str], dict]:",
     "def _context(req: GenerateDraftRequest, repo: Repository, document: Document | None = None) -> tuple[dict, list[str], dict]:")
edit(svc, '''    s = get_settings()
    now = clock.now()''', '''    company = effective(repo, get_settings())
    now = clock.now()''')
edit(svc, '''        "company_name": s.company_name,
        "company_name_latin": s.company_name_latin,
        "operator_name": s.operator_name if language == Language.bg else s.operator_name_latin,''', '''        "company_name": company.name,
        "company_name_latin": company.name_latin,
        "operator_name": company.operator_name if language == Language.bg else company.operator_name_latin,''')
edit(svc, "    if req.kind == DraftKind.payment_reminder:\n",
     "    if req.kind == DraftKind.payment_reminder and document is not None:\n"
     "        ctx |= document_invoice_context(document, language, now)  # no invoice record: facts from the file only\n"
     "    if req.kind == DraftKind.payment_reminder and document is None:\n")
edit(svc, "def generate_draft(req: GenerateDraftRequest, repo: Repository, llm: LLMClient) -> DraftMessage:\n    ctx, to, ids = _context(req, repo)",
     "def generate_draft(req: GenerateDraftRequest, repo: Repository, llm: LLMClient, document: Document | None = None) -> DraftMessage:\n    ctx, to, ids = _context(req, repo, document)")
edit(svc, "from app.drafting.document_context import recent_documents\n",
     "from app.company import effective\nfrom app.drafting.document_context import document_invoice_context, recent_documents\n")
edit(svc, "    DraftChannel,\n", "    Document,\n    DraftChannel,\n")
edit(svc, "from app.core.config import get_settings\n", "from app.core.config import get_settings\n")

# ---- document facts helpers
dctx = "app/drafting/document_context.py"
edit(dctx, '"""Facts already extracted from a client\'s documents, as LLM context for drafting. Never re-reads the files."""\n\nfrom app.repository import Repository\n',
     '"""Facts already extracted from a client\'s documents, as LLM context for drafting. Never re-reads the files."""\n\n'
     "from datetime import UTC, date, datetime, time\n\n"
     "from app.core.formatting import format_date\n"
     "from app.repository import Repository\n"
     "from app.schemas import Document, Language\n\n"
     'DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")\n')
s = open(dctx, encoding="utf-8").read() + '''

def due_date(fields: dict[str, str]) -> date | None:
    raw = (fields.get("due_date") or fields.get("maturity_date") or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def document_invoice_context(doc: Document, language: Language, now: datetime) -> dict:
    """Invoice fields for a payment reminder built from a file: only facts the file states."""
    f = doc.extracted_fields
    due = due_date(f)
    ctx = {
        "invoice_number": f.get("invoice_number"),
        "invoice_total": " ".join(x for x in (f.get("total_amount"), f.get("currency")) if x) or None,
        "invoice_due": format_date(datetime.combine(due, time(12), tzinfo=UTC), language) if due else None,
    }
    if due is not None:
        days = (due - now.date()).days
        if days >= 0:
            ctx["days_until_due"] = days
        else:
            ctx["days_overdue"] = -days
    return ctx
'''
open(dctx, "w", encoding="utf-8", newline="\n").write(s)

# ---- due-soon check: a client is enough to draft; invoice record is optional
dc = "app/events/document_checks.py"
s = open(dc, encoding="utf-8").read()
a = s.index("def _due_date(")
b = s.index("def _invoice_for(")
s = s[:a] + s[b:]
s = s.replace("    due = _due_date(doc.extracted_fields)\n", "    due = due_date(doc.extracted_fields)\n")
s = s.replace("from app.drafting.service import generate_draft\n", "from app.drafting.document_context import due_date\nfrom app.drafting.service import generate_draft\n")
s = s.replace("from datetime import date, datetime\n", "")
s = s.replace("DATE_FORMATS = (\"%Y-%m-%d\", \"%d.%m.%Y\", \"%d/%m/%Y\")\n", "")
start = s.index("    # Drafts are built only from our own invoice record")
s = s[:start] + '''    if client_id is None or event.draft_ids:
        return event  # nobody to address it to, or already drafted (even if the operator rejected it)
    pending = repo.drafts.list(
        where=lambda d: d.status in (DraftStatus.pending_review, DraftStatus.approved)
        and (d.event_id == event.id or (inv is not None and d.invoice_id == inv.id))
    )
    if pending:
        return event
    try:
        draft = generate_draft(
            GenerateDraftRequest(
                kind=DraftKind.payment_reminder,
                client_id=client_id,
                invoice_id=inv.id if inv else None,
                event_id=event.id,
                instructions=None if overdue else NOT_YET_DUE,
            ),
            repo,
            llm,
            document=None if inv else doc,
        )
        event = repo.events.upsert(event.model_copy(update={"draft_ids": [draft.id]}))
    except Exception as exc:  # the event stays; the operator can still draft by hand
        log.warning("reminder draft for %s failed: %s", doc.filename, type(exc).__name__)
    return event
'''
open(dc, "w", encoding="utf-8", newline="\n").write(s)

# ---- API: read and save company
d = "app/api/data.py"
edit(d, "from app.events.document_checks import recheck_documents\n",
     "from app.company import effective, save as save_company\nfrom app.events.document_checks import recheck_documents\nfrom app.schemas import CompanyInput\n")
edit(d, '@router.get("/trucks")', '''@router.get("/company")
def get_company(repo: Repository = Depends(get_repo)) -> CompanyInput:
    return effective(repo, get_settings())


@router.put("/company")
def put_company(body: CompanyInput, repo: Repository = Depends(get_repo), llm: LLMClient = Depends(get_llm)) -> CompanyInput:
    saved = save_company(repo, body)
    llm.set_company(saved.name, saved.operator_name)
    return effective(repo, get_settings())


@router.get("/trucks")''')

# ---- startup: LLM uses the saved company
main = "app/main.py"
edit(main, "    log.warning(\"LLM mode=%s model=%s | clock=%s\"",
     "    company = effective(repo, s)\n    get_llm().set_company(company.name, company.operator_name)\n    log.warning(\"LLM mode=%s model=%s | clock=%s\"")
edit(main, "from app.core.errors import ConflictError, NotFoundError\n",
     "from app.company import effective\nfrom app.core.errors import ConflictError, NotFoundError\n")
edit(main, "from app.deps import get_repo, get_seed\n", "from app.deps import get_llm, get_repo, get_seed\n")
print("ok")
