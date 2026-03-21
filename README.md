# Content Moderation API

An LLM-powered REST API that classifies user-generated content across four
categories — **toxicity, spam, PII, and off-topic** — returning typed
confidence scores. Built for platforms that need scalable, programmable content
moderation without a dedicated trust & safety team.

## The problem this solves

Marketplaces, forums, and review platforms need to moderate user submissions at
write-time — before they're stored or shown to other users. Regex rules break
as soon as product language changes. Human review doesn't scale. This API
accepts any text payload and returns a structured moderation decision in under
2 seconds.
