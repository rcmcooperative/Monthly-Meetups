<!--
TEMPLATE NOTES: delete this whole comment before publishing.

Structure and front matter follow the September 2026 recap (mm-recap-202609.md).
Placeholders are written {{LIKE_THIS}}. Highlighted text (<mark>) marks a decision or check for a person.

Filled from the pipeline's deterministic outputs (private/blog-YYYYMM/ and private/materials-YYYYMM/):
  {{AUTHORS}}           the whole "authors:" block, from blog-links.md ("Front matter: authors")
  {{HOSTS}} {{SPEAKER}} names already linked to their pages, from blog-links.md ("Host and speaker"),
                        read from docs/materials-YYYYMM/comms-copy.md
  {{REGISTERED}}        registration-digest.md. Check the report was generated after the meeting.
  {{REGISTER_URL}}  {{RECORDING_URL}} {{ARCHIVE_URL}} {{ISSUES_URL}} {{SUGGESTION_TEMPLATE}}
  {{NEXT_DATE}}  {{NEXT_TIME}}  {{NEXT_THEME}}  {{NEXT_HOSTS}}
                        session-inputs.json and blog-links.md. The next session's date, time and
                        theme are read from its Zoom registration page where possible, otherwise
                        supplied by the person.
  {{POLL_RESPONSES}} {{POLL_CAPACITY_PCT}} {{POLL_NETWORK_PCT}} {{POLL_ECOSYSTEM_PCT}}
                        poll-digest.md ("agree or strongly agree" column)
  {{MEETING_DATE}} {{MEETING_MONTH_NAME}} {{MONTH}}
                        the meetup month and the date in chat-digest.md

Suggested by Claude as options for a person to choose from (review/blog-options.md):
  {{EXCERPT}}           from the collaborative notes review
  {{BLOG_COVERAGE}}     the end of the sentence "This post summarises what we discussed ..."

Written by Claude from the source material:
  {{PURPOSE}}           chat-digest.md "Event purpose"
  {{WHAT_HAPPENED}}     the speaker's slides, the chat summary and the notes review.
                        Keep the structure: opening activity, the talk, each exercise in turn,
                        the collaborative output.
  {{FINDINGS}}          general findings or outcomes, from the notes review and the completed
                        exercises. High level: themes across the discussions, not a room-by-room account.
  {{WHAT_WORKED_HEADLINE}} {{WHAT_WORKED}}    poll-summary.md, chat-summary.md
  {{ROOM_TO_GROW}}      poll-summary.md, chat-summary.md, notes-review.md

Supplied by the team (not in the source material):
  {{TITLE}} {{BLOG_DATE}} {{ATTENDED}} {{SLACK_JOIN_INSTRUCTIONS}}
  {{IMAGE_SLUG}} {{IMAGE_ALT}}   asked for last, when the post is ready to go to the website repo:
                        the image file name and its description

Privacy and style:
  - High-level summary of the collaborative notes and chat. Never mention room numbers or
    individual breakout groups: write "in small groups" or "across the discussions".
  - No participant names, employers or places from the chat or notes. The host and speaker are
    named because they are named publicly in the invitation.
  - Link only to public material. Do not publish the CryptPad edit link or the Slack invite link.
  - UK English, one sentence per line.
-->

---
title: "{{TITLE}}: Reflections from Our {{MEETING_MONTH_NAME}} Monthly Meet-up"
date: {{BLOG_DATE}}
image: /assets/img/blog/mm-{{MONTH}}-{{IMAGE_SLUG}}.png
alt: {{IMAGE_ALT}}
excerpt: {{EXCERPT}}
{{AUTHORS}}
---

On {{MEETING_DATE}}, we hosted our {{MEETING_MONTH_NAME}} RCM Cooperative Monthly Meet-up.
{{REGISTERED}} people registered and <mark>{{ATTENDED}} joined us live (supply from the Zoom participants report)</mark>.
This post summarises what we discussed {{BLOG_COVERAGE}}.

This session was hosted by {{HOSTS}} and featured a presentation from {{SPEAKER}}.

<!-- If {{RECORDING_URL}} is "none", replace the next line with: "The recording will be published soon: we will add the link here." -->
You can rewatch the [recording of the session here]({{RECORDING_URL}}), with a summary of the discussion below.

# What happened

Our objectives for the session were {{PURPOSE}}.

{{WHAT_HAPPENED}}

## Findings from the session

{{FINDINGS}}

# What worked well

Feedback form responses suggest the session {{WHAT_WORKED_HEADLINE}}.
Of the {{POLL_RESPONSES}} people who responded, {{POLL_NETWORK_PCT}}% agreed or strongly agreed that the session connected them with others who can support their community work, {{POLL_ECOSYSTEM_PCT}}% that it strengthened their ability to describe or advocate for RCMs as a professional role, and {{POLL_CAPACITY_PCT}}% that it gave them skills, tools or practices to apply in their own community work.

{{WHAT_WORKED}}

# Room to grow

{{ROOM_TO_GROW}}

<!-- Use observations from the poll, the chat and the notes, framed constructively. To point readers
     at the notes, use: "see our [archive of this month's meetup here]({{ARCHIVE_URL}})". -->

# Join us next time

**Our next Monthly Meet-up is on {{NEXT_DATE}}, {{NEXT_TIME}}, and the theme is {{NEXT_THEME}}.**
<!-- Add "hosted by {{NEXT_HOSTS}}" when hosts are supplied. -->
[**Register here**]({{REGISTER_URL}}).

You can follow our progress in organising future sessions on the [Monthly Meetups issues page]({{ISSUES_URL}}).
To propose a session, [submit an issue]({{ISSUES_URL}}) using the "{{SUGGESTION_TEMPLATE}}" issue template.

You can find the materials from this session in our [public archive]({{ARCHIVE_URL}}).

We are also actively looking for speakers and call hosts to lead these sessions, who will each receive an honorarium for their contributions.
Speakers and hosts work with Core Members to develop the agenda, creating both an opportunity to showcase their expertise and be part of an expert community management team.
Hosts open and close the meeting and are supported by Core members to manage the breakout rooms, chat, and all backstage zoom activity, and they will also be invited to contribute to the blog summary.
We have a detailed event planning checklist for us all to work with and develop, helping each meetup to run more effectively than the last!
We are very pleased to support anyone who would like to host or speak at one of these sessions!

If you're curious about RCM Cooperative, please come along to a monthly meet-up!
You're also welcome to join our Slack workspace to share and meet with others: <mark>{{SLACK_JOIN_INSTRUCTIONS}} (do not paste the invite link from the chat)</mark>.

We look forward to seeing you at our [next meet-up]({{REGISTER_URL}})!
