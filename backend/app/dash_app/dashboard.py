"""
Dash + Plotly Interactive Dashboard.

Provides a full interactive dashboard mounted inside FastAPI.
Includes gauge chart, radar chart, bar chart, severity distribution,
issue table, executive summary, and recommendations panels.
"""

import json
import logging
from typing import Optional

import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

logger = logging.getLogger(__name__)

# Color theme matching the React frontend
COLORS = {
    "primary": "#1E3A8A",
    "good": "#16A34A",
    "warning": "#EAB308",
    "critical": "#DC2626",
    "background": "#F9FAFB",
    "card_bg": "#FFFFFF",
    "text": "#111827",
    "text_secondary": "#6B7280",
    "border": "#E5E7EB",
}

STATUS_COLORS = {
    "good": COLORS["good"],
    "warning": COLORS["warning"],
    "critical": COLORS["critical"],
}


def create_dash_app(flask_server=None) -> dash.Dash:
    """
    Create and configure the Dash application.

    Args:
        flask_server: Optional Flask/FastAPI server to mount Dash onto.

    Returns:
        Configured Dash application instance.
    """
    app = dash.Dash(
        __name__,
        server=False,
        url_base_pathname="/dashboard/",
        suppress_callback_exceptions=True,
    )

    app.layout = html.Div(
        style={
            "backgroundColor": COLORS["background"],
            "minHeight": "100vh",
            "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        },
        children=[
            # URL location
            dcc.Location(id="url", refresh=False),

            # Store for evaluation data
            dcc.Store(id="evaluation-store"),

            # Header
            html.Header(
                style={
                    "backgroundColor": COLORS["card_bg"],
                    "borderBottom": f"1px solid {COLORS['border']}",
                    "padding": "16px 40px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                },
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "12px"},
                        children=[
                            html.Div(
                                style={
                                    "width": "40px", "height": "40px",
                                    "borderRadius": "8px",
                                    "backgroundColor": COLORS["primary"],
                                    "display": "flex", "alignItems": "center",
                                    "justifyContent": "center",
                                    "color": "white", "fontWeight": "bold", "fontSize": "18px",
                                },
                                children="DQ",
                            ),
                            html.Span(
                                "DocQuality Dashboard",
                                style={"fontSize": "20px", "fontWeight": "600", "color": COLORS["text"]},
                            ),
                        ],
                    ),
                    html.Span(
                        "Interactive Evaluation Dashboard",
                        style={"fontSize": "14px", "color": COLORS["text_secondary"]},
                    ),
                ],
            ),

            # Main Content
            html.Main(
                id="dashboard-content",
                style={"maxWidth": "1200px", "margin": "0 auto", "padding": "32px 20px"},
                children=[
                    html.Div(
                        style={"textAlign": "center", "padding": "80px 20px"},
                        children=[
                            html.H2("Loading evaluation...", style={"color": COLORS["text"]}),
                            html.P(
                                "Evaluation data will be loaded from the URL path.",
                                style={"color": COLORS["text_secondary"]},
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    # Callback to load evaluation data and render dashboard
    @app.callback(
        Output("dashboard-content", "children"),
        Input("url", "pathname"),
    )
    def load_evaluation(pathname):
        """Load evaluation data based on URL path."""
        if not pathname or pathname == "/dashboard/":
            return _render_no_data()

        # Extract evaluation_id from path: /dashboard/{evaluation_id}
        parts = pathname.strip("/").split("/")
        if len(parts) < 2:
            return _render_no_data()

        evaluation_id = parts[-1]

        try:
            return _render_dashboard(evaluation_id)
        except Exception as e:
            logger.exception("Failed to render dashboard")
            return html.Div(
                style={"textAlign": "center", "padding": "80px"},
                children=[
                    html.H2("Error Loading Dashboard", style={"color": COLORS["critical"]}),
                    html.P(str(e), style={"color": COLORS["text_secondary"]}),
                ],
            )

    return app


def _render_no_data():
    """Render placeholder when no evaluation is loaded."""
    return html.Div(
        style={"textAlign": "center", "padding": "80px 20px"},
        children=[
            html.H2("No Evaluation Selected", style={"color": COLORS["text"]}),
            html.P(
                "Navigate to /dashboard/{evaluation_id} to view results.",
                style={"color": COLORS["text_secondary"], "marginTop": "8px"},
            ),
        ],
    )


def _render_dashboard(evaluation_id: str):
    """
    Render the full dashboard for an evaluation.

    Fetches data from the database and creates all chart components.
    """
    from app.database import SessionLocal
    from app.services.evaluation_orchestrator import EvaluationOrchestrator

    db = SessionLocal()
    try:
        orch = EvaluationOrchestrator()
        result = orch.get_evaluation_by_id(evaluation_id, db)

        if not result:
            return html.Div(
                style={"textAlign": "center", "padding": "80px"},
                children=[
                    html.H2("Evaluation Not Found", style={"color": COLORS["critical"]}),
                    html.P(
                        f"No evaluation found with ID: {evaluation_id}",
                        style={"color": COLORS["text_secondary"]},
                    ),
                ],
            )

        return html.Div(
            style={"display": "flex", "flexDirection": "column", "gap": "24px"},
            children=[
                # Overall Score Section
                _create_score_section(result),

                # Charts Row 1: Gauge + Radar
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "24px"},
                    children=[
                        _create_gauge_chart(result.overall_score, result.overall_status),
                        _create_radar_chart(result.metrics),
                    ],
                ),

                # Charts Row 2: Bar + Pie
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "24px"},
                    children=[
                        _create_bar_chart(result.metrics),
                        _create_severity_chart(result.issues),
                    ],
                ),

                # Executive Summary + Risk
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "24px"},
                    children=[
                        _create_summary_panel("Executive Summary", result.executive_summary),
                        _create_summary_panel("Risk Assessment", result.risk_summary),
                    ],
                ),

                # Recommendations
                _create_recommendations_panel(result.recommendations),

                # Issues Table
                _create_issues_table(result.issues),
            ],
        )
    finally:
        db.close()


def _card_style(**overrides):
    """Generate consistent card styling."""
    style = {
        "backgroundColor": COLORS["card_bg"],
        "borderRadius": "8px",
        "padding": "24px",
        "border": f"1px solid {COLORS['border']}",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
    }
    style.update(overrides)
    return style


def _create_score_section(result):
    """Create the overall score header section."""
    status_color = STATUS_COLORS.get(result.overall_status, COLORS["primary"])
    status_label = {
        "good": "Good Quality",
        "warning": "Moderate Quality",
        "critical": "Critical Issues Detected",
    }.get(result.overall_status, "Unknown")

    return html.Div(
        style=_card_style(),
        children=[
            html.Div(
                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "flexWrap": "wrap", "gap": "16px"},
                children=[
                    html.Div(children=[
                        html.H1(
                            f"Quality Score: {result.overall_score:.0f}/100",
                            style={"fontSize": "28px", "fontWeight": "700", "color": COLORS["text"], "margin": "0"},
                        ),
                        html.P(
                            f"File: {result.filename}",
                            style={"fontSize": "14px", "color": COLORS["text_secondary"], "margin": "4px 0 0"},
                        ),
                    ]),
                    html.Span(
                        status_label,
                        style={
                            "padding": "6px 16px",
                            "borderRadius": "6px",
                            "backgroundColor": f"{status_color}15",
                            "color": status_color,
                            "fontWeight": "600",
                            "fontSize": "14px",
                            "border": f"1px solid {status_color}30",
                        },
                    ),
                ],
            ),
        ],
    )


def _create_gauge_chart(score, status):
    """Create the gauge chart for overall score."""
    color = STATUS_COLORS.get(status, COLORS["primary"])

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "/100", "font": {"size": 28, "color": COLORS["text"]}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": COLORS["border"]},
            "bar": {"color": color, "thickness": 0.75},
            "bgcolor": "#F3F4F6",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 70], "color": "#FEE2E2"},
                {"range": [70, 90], "color": "#FEF3C7"},
                {"range": [90, 100], "color": "#DCFCE7"},
            ],
            "threshold": {
                "line": {"color": color, "width": 4},
                "thickness": 0.75,
                "value": score,
            },
        },
    ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"},
    )

    return html.Div(
        style=_card_style(),
        children=[
            html.H3("Overall Score", style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "16px"}),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ],
    )


def _create_radar_chart(metrics):
    """Create the radar chart for metric comparison."""
    categories = [m.name for m in metrics]
    values = [m.score for m in metrics]

    # Close the polygon
    categories.append(categories[0])
    values.append(values[0])

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill="toself",
        fillcolor="rgba(30, 58, 138, 0.15)",
        line=dict(color=COLORS["primary"], width=2),
        name="Score",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=12)),
        ),
        margin=dict(l=40, r=40, t=40, b=40),
        height=300,
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return html.Div(
        style=_card_style(),
        children=[
            html.H3("Metric Comparison", style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "16px"}),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ],
    )


def _create_bar_chart(metrics):
    """Create the bar chart for metric breakdown."""
    names = [m.name for m in metrics]
    scores = [m.score for m in metrics]
    colors = [STATUS_COLORS.get(m.status, COLORS["primary"]) for m in metrics]

    fig = go.Figure(go.Bar(
        x=names,
        y=scores,
        marker_color=colors,
        text=[f"{s:.0f}%" for s in scores],
        textposition="outside",
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        yaxis=dict(range=[0, 110], title="Score (%)", gridcolor="#F3F4F6"),
        xaxis=dict(title=""),
        margin=dict(l=40, r=20, t=20, b=40),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return html.Div(
        style=_card_style(),
        children=[
            html.H3("Metric Breakdown", style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "16px"}),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ],
    )


def _create_severity_chart(issues):
    """Create the pie/donut chart for issue severity distribution."""
    severity_counts = {"Critical": 0, "Warning": 0, "Minor": 0}
    for issue in issues:
        sev = issue.severity.lower()
        if sev == "critical":
            severity_counts["Critical"] += 1
        elif sev == "warning":
            severity_counts["Warning"] += 1
        else:
            severity_counts["Minor"] += 1

    labels = list(severity_counts.keys())
    values = list(severity_counts.values())
    chart_colors = [COLORS["critical"], COLORS["warning"], COLORS["good"]]

    if sum(values) == 0:
        return html.Div(
            style=_card_style(),
            children=[
                html.H3("Issue Distribution", style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "16px"}),
                html.Div(
                    style={"textAlign": "center", "padding": "60px 0"},
                    children=[
                        html.P("No issues detected", style={"color": COLORS["good"], "fontWeight": "600", "fontSize": "16px"}),
                    ],
                ),
            ],
        )

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.5,
        marker=dict(colors=chart_colors),
        textinfo="label+value",
        hovertemplate="%{label}: %{value} issue(s)<extra></extra>",
    ))

    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return html.Div(
        style=_card_style(),
        children=[
            html.H3("Issue Distribution", style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "16px"}),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ],
    )


def _create_summary_panel(title, content):
    """Create a summary text panel."""
    return html.Div(
        style=_card_style(),
        children=[
            html.H3(title, style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "12px"}),
            html.P(
                content or "No summary available.",
                style={
                    "color": COLORS["text_secondary"],
                    "fontSize": "14px",
                    "lineHeight": "1.6",
                },
            ),
        ],
    )


def _create_recommendations_panel(recommendations):
    """Create the recommendations panel."""
    if not recommendations:
        items = [html.Li("No recommendations available.", style={"color": COLORS["text_secondary"]})]
    else:
        items = [
            html.Li(
                rec,
                style={
                    "color": COLORS["text_secondary"],
                    "fontSize": "14px",
                    "lineHeight": "1.8",
                    "paddingLeft": "8px",
                },
            )
            for rec in recommendations
        ]

    return html.Div(
        style=_card_style(),
        children=[
            html.H3(
                "Recommendations",
                style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "12px"},
            ),
            html.Ul(
                children=items,
                style={"paddingLeft": "20px", "margin": "0"},
            ),
        ],
    )


def _create_issues_table(issues):
    """Create the interactive issues data table."""
    if not issues:
        return html.Div(
            style=_card_style(),
            children=[
                html.H3("Issues & Observations", style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "16px"}),
                html.P("No issues detected.", style={"color": COLORS["good"], "textAlign": "center", "padding": "40px"}),
            ],
        )

    df = pd.DataFrame([
        {
            "Field": i.field_name,
            "Type": i.issue_type,
            "Description": i.description,
            "Severity": i.severity.capitalize(),
        }
        for i in issues
    ])

    return html.Div(
        style=_card_style(),
        children=[
            html.H3("Issues & Observations", style={"fontSize": "18px", "fontWeight": "600", "color": COLORS["text"], "marginBottom": "16px"}),
            dash_table.DataTable(
                data=df.to_dict("records"),
                columns=[{"name": c, "id": c} for c in df.columns],
                filter_action="native",
                sort_action="native",
                sort_mode="multi",
                page_size=10,
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": "#F9FAFB",
                    "fontWeight": "600",
                    "fontSize": "13px",
                    "color": COLORS["text"],
                    "borderBottom": f"2px solid {COLORS['border']}",
                    "padding": "12px",
                },
                style_cell={
                    "fontSize": "13px",
                    "padding": "10px 12px",
                    "color": COLORS["text"],
                    "borderBottom": f"1px solid {COLORS['border']}",
                    "textAlign": "left",
                },
                style_data_conditional=[
                    {
                        "if": {"filter_query": '{Severity} = "Critical"'},
                        "backgroundColor": "#FEE2E2",
                        "color": COLORS["critical"],
                    },
                    {
                        "if": {"filter_query": '{Severity} = "Warning"'},
                        "backgroundColor": "#FEF3C7",
                        "color": "#92400E",
                    },
                    {
                        "if": {"filter_query": '{Severity} = "Good"'},
                        "backgroundColor": "#DCFCE7",
                        "color": COLORS["good"],
                    },
                ],
            ),
        ],
    )
