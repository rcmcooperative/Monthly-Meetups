---
title: |
  \vspace{-4cm}
  \includegraphics[width=\textwidth]{../../assets/logos-rcm-neuro.png} \par \vspace{0.5cm}
  Briefing Note on Tanenbaum Open Science Institute (TOSI) Open Scientist in Residence Program (OSRP) 2025
author: "Cassandra Gould van Praag, Executive Director, RCM Cooperative"
date: "March 2026"
papersize: a4
geometry:
  - top=1.5cm
  - bottom=3cm
  - left=2.5cm
  - right=2.5cm
  - headheight=3.5cm
  - includehead
  - headsep=0.5cm
header-includes:
  - \usepackage{parskip} # Removes indents and adds space
  - \raggedright
  - \usepackage{booktabs}
  - \usepackage{longtable}
  - \usepackage{graphicx}
  - \usepackage{fontspec}
  - \usepackage{fancyhdr}
  - \usepackage{etoolbox}
  - \usepackage{rotating}
  - \usepackage{caption}
  - \usepackage{xcolor}
  - \renewcommand{\contentsname}{Table of Contents}
  - \setcounter{tocdepth}{2}
#   - \setcounter{secnumdepth}{4}
  # Hyperref configuration
  - \usepackage[unicode]{hyperref}
  - |
    \hypersetup{
        colorlinks=true,
        linkcolor=blue,
        hidelinks
    }
  # Global Style Definition
  - \pagestyle{fancy}
  - \fancyhf{}
  - \fancyhead[C]{\includegraphics[width=\textwidth]{../../assets/logos-rcm-neuro.png}}
  - \fancyfoot[L]{ADR UK Community Recommendations}
  - \fancyfoot[R]{\thepage}
  - \renewcommand{\headrulewidth}{0pt}
  - \renewcommand{\footrulewidth}{0.4pt}
  # Adjust Title Spacing
  - \makeatletter
  - \patchcmd{\@maketitle}{\vskip 2em}{\vskip 0.2em}{}{}
  - \makeatother
  # Custom commands
  - |
    \newcommand{\tableimagelandscape}[3]{
      \newpage
      \begin{sidewaystable}
        \centering
        \captionsetup{font={bf, normalsize}, position=top}
        \caption{#1} 
        \label{#3} 
        \vspace{10pt}
        \includegraphics[width=0.95\textheight, keepaspectratio]{#2}
      \end{sidewaystable}
      \newpage
    }
  - \newcommand{\tabref}[1]{\hyperref[#1]{\textcolor{blue}{Table~\ref{#1}}}}
  - \newcommand{\figref}[1]{\hyperref[#1]{\textcolor{blue}{Figure~\ref{#1}}}}
mainfont: "Arial"
fontsize: 11pt
---

<!-- build with `pandoc briefing-note.md -o briefing-note.pdf --pdf-engine=xelatex -V colorlinks=true -V linkcolor=blue -V urlcolor=blue` -->

\thispagestyle{fancy}
<!-- % Hide logo on page 1 only -->
\fancyhead[C]{} 
<!-- \tableofcontents

\newpage -->
<!-- % Reset the header logo for all subsequent pages -->
<!-- \fancyhead[C]{\includegraphics[width=\textwidth]{../assets/logo-rcm-adr.png}} -->


# Project overview

# Strategic objectives & methodology


# Outcomes
- **Outcome 1**: 
- **Outcome 2**: 
- **Outcome 3**: 

# Impact
Requested testimonial with link to individual institutional profile: 

- How did your confidence in working with your community change from the start of the training and community clinics to the end?

- How did the tools or frameworks we provided change the way you manage your time in working with your community?

- How have the skills you learned impacted your other research activities (e.g., communicating or collaborating)?

- Was there a specific 'aha!' moment or a piece of understanding that was particularly important for you?

# What happened next


# Our specialised service model
RCM Cooperative leverages the breadth of our expertise to bring bespoke community solutions to your organisation.
- Professional RCM Training: We deliver the RCM101 curriculum, tailored to your sector’s specific technical and social requirements.
- Strategic Coaching & Mentorship: We offer "Community Clinics" to help project leads navigate complex member environments and build consensus.
- Open Infrastructure Design: We provide technical expertise in setting up equitable collaboration tools (e.g., GitHub, Slack) and documented workflows to ensure operational transparency.

Take a look at the [github repo we used for managing and archiving materials for this project]



