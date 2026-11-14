import streamlit as st


# ==========================================
# Built-in OS Demo Notes (~800 words)
# ==========================================
DEMO_DOCUMENT_TEXT = """
--- Document: SmartStudy_AI_Demo_OS_Notes.pdf ---

OPERATING SYSTEMS: DEADLOCKS & BANKER'S ALGORITHM
Comprehensive Lecture Notes | Computer Science Engineering

======================================================
1. INTRODUCTION TO DEADLOCKS
======================================================

A deadlock is a situation in a multiprogramming operating system where two or more
processes are waiting indefinitely for each other to release resources, resulting in
a complete standstill where none of the involved processes can proceed.

Deadlocks arise in systems where resources are non-preemptible (cannot be forcibly
taken from a process), and processes hold some resources while waiting for others.

Coffman Conditions (All 4 must hold simultaneously for deadlock):
  (a) Mutual Exclusion: At least one resource must be non-shareable; only one
      process may use it at any time.
  (b) Hold and Wait: A process must be holding at least one resource and waiting
      to acquire additional resources held by other processes.
  (c) No Preemption: Resources cannot be forcibly removed from a process; they
      must be released voluntarily.
  (d) Circular Wait: A closed chain P1 -> P2 -> ... -> Pn -> P1 must exist where
      each process waits for a resource held by the next.

Deadlock vs Starvation:
  - Deadlock: Permanent blockage of a set of processes (circular dependency).
  - Starvation: A process is indefinitely delayed because other processes
    continuously get preference, but it is not blocked in a circular chain.

======================================================
2. DEADLOCK HANDLING STRATEGIES
======================================================

(A) DEADLOCK PREVENTION
  Eliminate at least one Coffman condition at design time:
  - Break Mutual Exclusion: Use sharable resources (e.g., read-only files).
  - Break Hold and Wait: Require a process to request all resources upfront
    before execution begins.
  - Allow Preemption: If a process cannot get all resources, release what it
    holds and retry.
  - Break Circular Wait: Impose a total ordering on resource types; processes
    must request resources in increasing order.
  Limitation: Prevention is often overly restrictive and reduces system throughput.

(B) DEADLOCK AVOIDANCE
  The system dynamically grants resources only if doing so keeps the system in
  a safe state. Requires advance knowledge of maximum resource needs.
  Key Concept - Safe State: A state is safe if there exists a safe sequence
  P1, P2, ..., Pn such that all resource requests of each Pi can be satisfied
  using currently available resources plus resources held by processes Pj (j < i).

(C) DEADLOCK DETECTION AND RECOVERY
  Allow deadlocks to occur, detect them using a resource allocation graph or
  detection algorithm, and recover:
  - Recovery by Process Termination: Abort one or more deadlocked processes.
  - Recovery by Resource Preemption: Preempt resources and roll back processes.

(D) DEADLOCK IGNORANCE (Ostrich Algorithm)
  Ignore the problem and assume deadlocks will rarely occur. Used in most
  general-purpose operating systems (e.g., UNIX, Windows) where the cost
  of prevention/avoidance outweighs the rare occurrence of deadlock.

======================================================
3. BANKER'S ALGORITHM (DEADLOCK AVOIDANCE)
======================================================

The Banker's Algorithm, proposed by Edsger Dijkstra, is a deadlock avoidance
algorithm used in operating systems. It models a bank that lends resources only
when it can guarantee that all clients (processes) can eventually be satisfied.

Key Data Structures (n = number of processes, m = number of resource types):

  - Available[m]:      Number of available instances of each resource type.
  - Max[n][m]:         Maximum demand of each process for each resource type.
  - Allocation[n][m]:  Number of resources of each type currently allocated.
  - Need[n][m]:        Remaining resource need. Need[i][j] = Max[i][j] - Allocation[i][j].

Safety Algorithm (Checks if a state is safe):
  Step 1: Initialize Work = Available and Finish[i] = false for all i.
  Step 2: Find process Pi where Finish[i] = false AND Need[i] <= Work.
  Step 3: If found: Work = Work + Allocation[i]; Finish[i] = true. Goto Step 2.
  Step 4: If Finish[i] = true for all i, the system is in a safe state.

Resource Request Algorithm (Handles a resource request by Pi):
  Step 1: If Request[i] <= Need[i], go to Step 2. Else error (exceeded max claim).
  Step 2: If Request[i] <= Available, go to Step 3. Else Pi must wait.
  Step 3: Pretend to allocate:
            Available = Available - Request[i]
            Allocation[i] = Allocation[i] + Request[i]
            Need[i] = Need[i] - Request[i]
  Step 4: Run the Safety Algorithm. If safe, complete allocation. If unsafe,
          restore old state and make Pi wait.

Advantages of Banker's Algorithm:
  - Guarantees the system never enters an unsafe (deadlock-prone) state.
  - More flexible and efficient than strict deadlock prevention.

Limitations of Banker's Algorithm:
  - Requires advance knowledge of maximum resource needs (impractical in general).
  - Processes must be finite and have a fixed maximum demand.
  - High overhead for large systems due to repeated safety checks.
  - Not applicable to real-time systems where response time is critical.

======================================================
4. RESOURCE ALLOCATION GRAPH (RAG)
======================================================

A Resource Allocation Graph is a directed graph used to represent the state of
resource allocation in a system:
  - Process nodes (circles): Represent processes P1, P2, ...
  - Resource nodes (squares with dots): Each dot = one resource instance.
  - Request edge (Pi -> Rj): Process Pi is requesting resource Rj.
  - Assignment edge (Rj -> Pi): Resource Rj is assigned to process Pi.

Deadlock Detection using RAG:
  - Single-instance resources: A cycle in the RAG indicates deadlock.
  - Multi-instance resources: A cycle is necessary but not sufficient; use
    the deadlock detection algorithm.

======================================================
5. EXAM TIPS & KEY FORMULAS
======================================================

Need[i][j] = Max[i][j] - Allocation[i][j]

Minimum resources to guarantee no deadlock (for n processes, each needing max k):
  Minimum resources = n * (k - 1) + 1

Safe sequence: A permutation of processes such that each process's remaining
needs can be met with currently available + resources of earlier processes.
""".strip()


def apply_custom_styles(dark_mode: bool = False) -> None:
    """Injects modern SaaS CSS styling with Light or Dark Mode support."""

    if dark_mode:
        # Dark Mode palette
        bg         = "#0F172A"
        surface    = "#1E293B"
        surface2   = "#273549"
        border     = "#334155"
        border_acc = "#4F46E5"
        text_main  = "#F8FAFC"
        text_muted = "#94A3B8"
        text_card  = "#CBD5E1"
        accent     = "#818CF8"
        accent_dk  = "#6366F1"
        shadow     = "rgba(0,0,0,0.4)"
        shadow_acc = "rgba(129,140,248,0.15)"
        hero_grad  = "linear-gradient(135deg, #3730A3 0%, #1E1B4B 100%)"
        hero_badge = "rgba(255,255,255,0.12)"
        summary_bg = "#1E293B"
        summary_lft= "#818CF8"
        summary_hv = "#273549"
        metric_hv  = "#273549"
        auth_bg    = "#1E293B"
        auth_brd   = "#334155"
        exp_bg     = "#1E293B"
        chat_bg    = "#1E293B"
        btn_p      = "#6366F1"
        btn_phv    = "#4F46E5"
        tab_active = "#818CF8"
    else:
        # Light Mode palette
        bg         = "#FFFFFF"
        surface    = "#FFFFFF"
        surface2   = "#F8FAFC"
        border     = "#E2E8F0"
        border_acc = "#C7D2FE"
        text_main  = "#0F172A"
        text_muted = "#64748B"
        text_card  = "#1E293B"
        accent     = "#4F46E5"
        accent_dk  = "#4338CA"
        shadow     = "rgba(0,0,0,0.04)"
        shadow_acc = "rgba(79,70,229,0.08)"
        hero_grad  = "linear-gradient(135deg, #4F46E5 0%, #3730A3 100%)"
        hero_badge = "rgba(255,255,255,0.15)"
        summary_bg = "#F8FAFC"
        summary_lft= "#4F46E5"
        summary_hv = "#F1F5F9"
        metric_hv  = "#FFFFFF"
        auth_bg    = "#FFFFFF"
        auth_brd   = "#E2E8F0"
        exp_bg     = "#F8FAFC"
        chat_bg    = "#FFFFFF"
        btn_p      = "#4F46E5"
        btn_phv    = "#4338CA"
        tab_active = "#4F46E5"

    custom_css = f"""
    <style>
        /* 1. Global Background & Text (Dark Mode override) */
        .stApp {{
            background-color: {bg} !important;
        }}
        .main .block-container {{
            background-color: {bg} !important;
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }}
        body, p, div, label, span, li, td, th {{
            color: {text_main} !important;
        }}

        /* 2. Hide default Streamlit chrome */
        #MainMenu, header, footer {{ visibility: hidden; }}
        div[data-testid="stToolbar"] {{ visibility: hidden; display: none; }}
        div[data-testid="stDecoration"] {{ display: none; }}

        /* 3. Welcome SaaS Hero Banner */
        .welcome-hero {{
            background: {hero_grad};
            color: #FFFFFF;
            padding: 24px 28px;
            border-radius: 16px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(79,70,229,0.25);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .welcome-hero h2 {{
            color: #FFFFFF !important;
            margin: 0 0 6px 0 !important;
            font-size: 1.6rem !important;
            font-weight: 700 !important;
        }}
        .welcome-hero p {{ color: #E0E7FF !important; margin: 0 !important; font-size: 0.95rem !important; }}
        .welcome-stats-badge {{
            background: {hero_badge};
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255,255,255,0.25);
            padding: 8px 16px;
            border-radius: 9999px;
            font-size: 0.88rem;
            font-weight: 600;
            color: #FFFFFF;
        }}

        /* 4. Auth Card */
        .auth-header {{ text-align: center; margin-bottom: 24px; }}
        .auth-header h1 {{
            font-size: 1.85rem !important;
            font-weight: 800 !important;
            color: {accent} !important;
            margin-bottom: 8px !important;
        }}
        .auth-header p {{ color: {text_muted} !important; font-size: 0.95rem !important; margin: 0 !important; }}

        /* 5. Metric Cards */
        div[data-testid="stMetric"] {{
            background-color: {surface} !important;
            border: 1px solid {border} !important;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 1px 3px {shadow};
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        }}
        div[data-testid="stMetric"]:hover {{
            transform: translateY(-2px);
            border-color: {border_acc} !important;
            box-shadow: 0 8px 20px {shadow_acc};
        }}
        div[data-testid="stMetric"] label {{
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            color: {text_muted} !important;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: {text_main} !important;
        }}

        /* 6. Flashcard & Container Borders */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 12px !important;
            border-color: {border} !important;
            background-color: {surface} !important;
            box-shadow: 0 1px 3px {shadow} !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
            transform: translateY(-2px);
            border-color: {border_acc} !important;
            box-shadow: 0 8px 20px {shadow_acc} !important;
        }}

        /* 7. Summary Cards */
        .summary-card {{
            background-color: {summary_bg};
            border: 1px solid {border};
            border-left: 4px solid {summary_lft};
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 12px;
            font-size: 0.98rem;
            line-height: 1.55;
            color: {text_card};
            transition: transform 0.15s ease, background-color 0.15s ease;
        }}
        .summary-card:hover {{
            transform: translateX(3px);
            background-color: {summary_hv};
        }}

        /* 8. Buttons */
        button[kind="primary"] {{
            background-color: {btn_p} !important;
            border-color: {btn_p} !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }}
        button[kind="primary"]:hover {{
            background-color: {btn_phv} !important;
            border-color: {btn_phv} !important;
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(79,70,229,0.25) !important;
        }}
        button[kind="secondary"] {{
            border-radius: 10px !important;
            font-weight: 500 !important;
            background-color: {surface} !important;
            border-color: {border} !important;
            color: {text_main} !important;
            transition: all 0.2s ease !important;
        }}
        button[kind="secondary"]:hover {{
            border-color: {accent} !important;
            background-color: {surface2} !important;
        }}

        /* 9. Tabs */
        div[data-testid="stTabs"] button[role="tab"] {{
            font-size: 0.95rem;
            font-weight: 600;
            padding: 10px 18px;
            border-radius: 8px 8px 0 0;
            color: {text_muted} !important;
            background-color: transparent !important;
            transition: color 0.15s ease;
        }}
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
            color: {tab_active} !important;
            border-bottom: 2px solid {tab_active} !important;
        }}

        /* 10. Expanders */
        div[data-testid="stExpander"] {{
            border: 1px solid {border} !important;
            border-radius: 10px !important;
            background-color: {exp_bg} !important;
            overflow: hidden;
        }}
        div[data-testid="stExpander"] summary {{
            color: {text_main} !important;
        }}

        /* 11. Chat Bubbles */
        div[data-testid="stChatMessage"] {{
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 12px;
            border: 1px solid {border};
            background-color: {chat_bg};
            box-shadow: 0 1px 2px {shadow};
        }}

        /* 12. Sidebar — locked open; collapse/expand controls hidden */
        [data-testid="stSidebar"] {{
            background-color: {surface} !important;
            border-right: 1px solid {border} !important;
            min-width: 280px !important;
            max-width: 320px !important;
            transform: none !important;
        }}
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"] {{
            display: none !important;
        }}
        [data-testid="stSidebar"] * {{
            color: {text_main} !important;
        }}
        [data-testid="stSidebar"] button {{
            text-align: left !important;
            justify-content: flex-start !important;
            border-radius: 8px !important;
            font-size: 0.88rem !important;
            background-color: {surface2} !important;
            border-color: {border} !important;
        }}

        /* 13. Text inputs */
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {{
            background-color: {surface2} !important;
            border-color: {border} !important;
            color: {text_main} !important;
            border-radius: 8px !important;
        }}

        /* 14. Selectbox & Radio */
        div[data-testid="stSelectbox"] > div,
        div[data-baseweb="select"] {{
            background-color: {surface2} !important;
            border-color: {border} !important;
            color: {text_main} !important;
            border-radius: 8px !important;
        }}

        /* 15. Info / Success / Warning / Error boxes */
        div[data-testid="stAlert"] {{
            border-radius: 10px !important;
            border-left-width: 4px !important;
        }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
