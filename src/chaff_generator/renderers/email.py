"""EML renderer — stdlib EmailMessage, LF newlines (spec sections 12, 66, 74).

Builds an :class:`EmailDocument` from the picked email template, then
serializes it as a standards-compliant ``.eml``: proper ``From``/``To``/
``Date``/``Message-ID`` headers, occasional ``In-Reply-To``/``References``
threading with monotonically dated parents, a ``multipart/alternative``
body (plain + HTML), and attachments generated **entirely in memory** —
attachment bytes never touch the host filesystem.
"""

from __future__ import annotations

import email.utils
from datetime import datetime
from email import policy
from email.message import EmailMessage
from typing import TYPE_CHECKING

from chaff_generator.content import builders
from chaff_generator.content import generators as gen
from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.documents import EmailDocument
from chaff_generator.renderers.textutil import finish, open_writer

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument
    from chaff_generator.templates.models import TemplateDef

CAPABILITIES = RendererCapabilities(
    extension="eml",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=False,
    semantic_document="email",
    size_category="email",
)

#: Body target as a fraction of desired size (headers and MIME framing add
#: the rest; eml is an approximate-size format).
_BODY_FRACTION = 0.85

#: The visible text body stops at this fraction; on larger targets the rest
#: of the volume goes to an attachment (short mail, fat attachment).
_BODY_TEXT_FRACTION = 0.6

#: Attachment prose tops a body up in ~4 KiB paragraphs.
_ATTACHMENT_PARAGRAPH_BYTES = 4 << 10


def build_email_document(template: TemplateDef, context: RenderContext) -> EmailDocument:
    """Materialize an email template into an EmailDocument."""
    from chaff_generator.renderers.documents import EmailAttachment

    engine = context.template_engine
    rng = context.rng
    body = template.body

    sender = context.world.primary_user
    pool = context.world.contacts or context.world.employees or [sender]
    recipient = gen.pick(rng, pool)

    subject = engine.render_string(str(body.get("subject", "Project update")), {})
    from_name = engine.render_string(str(body.get("from_name", "{{ primary_user.full_name }}")), {})
    to_name = engine.render_string(
        str(body.get("to_name", "{{ person.full_name }}")), {"person": recipient}
    )

    timeline = context.world.timeline
    if timeline is not None:
        day = timeline.draw_between(rng)
        sent_at = datetime.combine(
            day,
            datetime.min.time().replace(hour=rng.randrange(8, 19), minute=rng.randrange(60)),
        )
    else:
        sent_at = datetime(2025, 6, 15, 9, 30)

    paragraphs = [engine.render_string(str(item), {}) for item in body.get("body_paragraphs", [])]
    str(body.get("category", "business"))
    signature = engine.render_string(str(body.get("signature", "")), {})

    # Scale the body toward its share of the target volume with filler
    # paragraphs (approximate format: no exact-size contract).
    body_text = "\n\n".join(paragraphs)
    body_target = int(context.desired_size * _BODY_TEXT_FRACTION)
    while len(body_text) < body_target and len(paragraphs) < 4_000:
        filler = builders.filler_paragraph(context, sentences=rng.randrange(2, 5))
        paragraphs.append(filler)
        body_text = "\n\n".join(paragraphs)

    message_id = f"<{gen.make_id('msg', rng)}@{sender.email.split('@')[-1]}>"
    references: list[str] = []
    in_reply_to: str | None = None
    if rng.random() < 0.3:  # some mail sits inside a thread
        parent = f"<{gen.make_id('msg', rng)}@{sender.email.split('@')[-1]}>"
        references.append(parent)
        in_reply_to = parent

    attachments: list[EmailAttachment] = []
    fill_target = int(context.desired_size * _BODY_FRACTION)
    remaining = fill_target - len(body_text)
    if remaining > _ATTACHMENT_PARAGRAPH_BYTES:
        attachment = _attachment_text(context, remaining)
        if attachment is not None:
            attachments.append(attachment)

    return EmailDocument(
        subject=subject,
        from_name=from_name,
        from_email=sender.email,
        to_name=to_name,
        to_email=recipient.email,
        sent_at=sent_at,
        body_plain=f"{body_text}\n\n{signature}",
        cc=_cc_list(context, rng),
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        attachments=attachments,
    )


def _cc_list(context: RenderContext, rng) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
    pool = context.world.employees
    if not pool or rng.random() > 0.35:
        return []
    chosen = gen.pick(rng, pool)
    return [(chosen.full_name, chosen.email)]


def _attachment_text(context: RenderContext, budget: int):  # type: ignore[no-untyped-def]
    """A prose .txt attachment generated wholly in memory (never a host file)."""
    from chaff_generator.renderers.documents import EmailAttachment

    chunks: list[str] = [
        f"Notes prepared by {context.world.primary_user.full_name}",
        "",
    ]
    written = sum(len(part) + 1 for part in chunks)
    while written < budget:
        paragraph = builders.filler_paragraph(context, sentences=6)
        chunks.append(paragraph)
        written += len(paragraph) + 1
    content = ("\n".join(chunks) + "\n").encode()
    return EmailAttachment(
        filename=f"notes-{context.rng.randrange(100, 999)}.txt",
        mime_type="text/plain",
        content=content,
    )


def _html_body(document: EmailDocument) -> str:
    import html as html_module

    paragraphs = [p for p in document.body_plain.split("\n\n") if p.strip()]
    rendered = "\n".join(
        f"  <p>{html_module.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs
    )
    return f"<!DOCTYPE html>\n<html>\n<body>\n{rendered}\n</body>\n</html>\n"


class EmailRenderer:
    id = "eml"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        if document is None:
            if context.template_id is None:
                # No template: synthesize one so bare .eml files still carry
                # a full, template-driven body.
                document = build_email_document(_fallback_email_template(context), context)
            else:
                template = context.bank.templates().require(context.template_id)
                document = build_email_document(template, context)
        assert isinstance(document, EmailDocument)  # narrowed: builder above

        message = EmailMessage(policy=policy.default.clone(linesep="\n"))
        message["From"] = email.utils.formataddr((document.from_name, document.from_email))
        message["To"] = email.utils.formataddr((document.to_name, document.to_email))
        for name, address in document.cc:
            message["Cc"] = email.utils.formataddr((name, address))
        message["Subject"] = document.subject
        message["Date"] = email.utils.format_datetime(document.sent_at)
        message["Message-ID"] = document.message_id
        if document.in_reply_to:
            message["In-Reply-To"] = document.in_reply_to
        if document.references:
            message["References"] = " ".join(document.references)
        message["X-Mailer"] = f"Chaff Generator {context.app_version}"

        message.set_content(document.body_plain)
        message.add_alternative(_html_body(document), subtype="html")
        for attachment in document.attachments:
            message.add_attachment(
                attachment.content,
                maintype=attachment.mime_type.split("/")[0],
                subtype=attachment.mime_type.split("/")[1],
                filename=attachment.filename,
            )

        # stdlib randomizes MIME boundaries per serialization (outer part and
        # every multipart subpart); pin them all from the file's RNG so the
        # same seed yields byte-identical .eml files.
        for part in message.walk():
            if part.is_multipart():
                part.set_boundary(f"=_chaff-{gen.make_id('bnd', context.rng)}")

        payload = message.as_bytes()
        handle, writer = open_writer(destination)
        with handle:
            writer.write(payload)
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def _fallback_email_template(context: RenderContext):  # type: ignore[no-untyped-def]
    """A minimal in-memory template for template-less .eml plans."""
    from chaff_generator.templates.models import TemplateDef

    return TemplateDef(
        id="email.fallback",
        kind="email",
        description="Synthesized fallback email",
        body={
            "subject": "{{ word('topics') | title }} update",
            "from_name": "{{ primary_user.full_name }}",
            "to_name": "{{ person.full_name }}",
            "category": "business",
            "body_paragraphs": [
                "{{ pick('greetings') }}",
                "{{ sentence('business') }}",
                "{{ paragraph('business', 2) }}",
                "{{ pick('closings') }}",
            ],
            "signature": "{{ primary_user.full_name }}\n{{ organization.name }}",
        },
    )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "eml":
        raise ValueError(f"email module cannot serve renderer id {renderer_id!r}")
    return EmailRenderer()
