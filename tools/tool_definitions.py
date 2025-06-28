# tools/tool_definitions.py

from google.genai.types import Tool, FunctionDeclaration
from typing import List, Any, Dict
import streamlit as st
from tools.social_media_tool import SocialMediaAggregator
from tools.job_compatibility_tool import JobCompatibilityAnalyzer
from tools.pdf_generator import JobCompatibilityPDFGenerator
from datetime import datetime

class ToolDefinitions:
    """Tool definitions for function calling"""

    def __init__(self):
        self.social_media_aggregator = SocialMediaAggregator()
        self.job_compatibility_analyzer = None  # Will be initialized with client and CV data
        self.pdf_generator = JobCompatibilityPDFGenerator()

    def initialize_job_analyzer(self, client, cv_data, rag_system=None):
        """Initialize job compatibility analyzer with RAG system reference"""
        try:
            from tools.job_compatibility_tool import JobCompatibilityAnalyzer
            self.job_compatibility_analyzer = JobCompatibilityAnalyzer(client, cv_data, rag_system)
            return True
        except Exception as e:
            print(f"Error initializing job analyzer: {e}")
            return False

    @staticmethod
    def get_pdf_generation_tool_definition() -> Tool:
        """Get PDF generation tool definition."""
        generate_pdf_func = FunctionDeclaration(
            name="generate_compatibility_pdf",
            description="Generates a PDF of the most recently created job compatibility report. "
                    "This tool is often called automatically after job analysis when PDF is requested. "
                    "Use this when the user asks to download, save, or get a PDF of the analysis.",
            parameters={"type": "object", "properties": {}}  # No parameters needed
        )

        return Tool(function_declarations=[generate_pdf_func])

    @staticmethod
    def get_email_tool_definition() -> Tool:
        """Get email tool definition for function calling"""
        prepare_email_func = FunctionDeclaration(
            name="prepare_email",
            description="Prepare an email to Selman when someone wants to contact him. This function prepares the email for review before sending.",
            parameters={
                "type": "object",
                "properties": {
                    "sender_name": {
                        "type": "string",
                        "description": "Name of the person sending the email"
                    },
                    "sender_email": {
                        "type": "string",
                        "description": "Email address of the sender"
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content to send to Selman"
                    }
                },
                "required": ["sender_name", "sender_email", "message"]
            }
        )

        return Tool(function_declarations=[prepare_email_func])

    @staticmethod
    def get_social_media_tool_definition() -> Tool:
        """Get social media aggregator tool definition"""
        get_posts_func = FunctionDeclaration(
            name="get_recent_posts",
            description="Get Selman's recent posts from Medium. Use this when someone asks about his latest posts, articles, or social media activity.",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of posts to retrieve (default: 5)",
                        "default": 5
                    },
                    "search_query": {
                        "type": "string",
                        "description": "Optional search query to filter posts by topic"
                    }
                },
                "required": []
            }
        )

        return Tool(function_declarations=[get_posts_func])

    @staticmethod
    def get_job_compatibility_tool_definition() -> Tool:
        """Get job compatibility analysis tool definition with language selection"""
        analyze_job_func = FunctionDeclaration(
            name="analyze_job_compatibility",
            description="Analyze job compatibility between Selman's profile and a job description. Use this when someone provides a job posting or asks about fit for a specific role.",
            parameters={
                "type": "object",
                "properties": {
                    "job_description": {
                        "type": "string",
                        "description": "The full job description text to analyze compatibility against"
                    },
                    "report_language": {
                        "type": "string",
                        "description": "Language for the compatibility report. ALWAYS ask the user to choose between English (en) or Turkish (tr) before proceeding.",
                        "enum": ["en", "tr"]
                    },
                    "company_name": {
                        "type": "string",
                        "description": "Name of the company. If the user does not provide the company name, you MUST ask for it by responding with: 'Could you please specify for which company are you asking for this report?'"
                    }
                },
                "required": ["job_description", "report_language", "company_name"]
            }
        )

        return Tool(function_declarations=[analyze_job_func])

    def get_all_tools(self) -> List[Tool]:
        """Get all available tools"""
        return [
            self.get_email_tool_definition(),
            self.get_social_media_tool_definition(),
            self.get_job_compatibility_tool_definition(),
            self.get_pdf_generation_tool_definition()
        ]

    def execute_tool(self, tool_name: str, tool_args: Dict) -> Dict[str, Any]:
        """Execute the requested tool"""
        if tool_name == "prepare_email":
            # Add default subject
            tool_args['subject'] = "New Message from Portfolio Bot"
            # Store email data for verification
            st.session_state.pending_email = tool_args
            return {
                "success": True,
                "message": "Email prepared for review",
                "data": tool_args
            }

        elif tool_name == "get_recent_posts":
            try:
                limit = tool_args.get('limit', 5)
                search_query = tool_args.get('search_query', '')

                # Get Medium posts only
                posts = self.social_media_aggregator.get_medium_posts(limit)

                # Filter by search query if provided
                if search_query and posts:
                    formatted_posts = self.social_media_aggregator.get_post_summary(search_query, posts)
                else:
                    # Detect language from session state
                    language = "tr" if any("tr" in str(msg).lower() for msg in st.session_state.get("messages", [])) else "en"
                    formatted_posts = self.social_media_aggregator.format_posts_for_chat(posts, language)

                return {
                    "success": True,
                    "message": "Posts retrieved successfully",
                    "data": {
                        "posts": posts,
                        "formatted_response": formatted_posts,
                        "count": len(posts)
                    }
                }

            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error retrieving posts: {str(e)}"
                }

        elif tool_name == "generate_compatibility_pdf":
            try:
                # Get report content and job title from session state
                report_content = st.session_state.get("last_compatibility_report")
                job_title = st.session_state.get("last_job_title", "Unknown Position")
                company_name = st.session_state.get("last_company_name", "Unknown Company")
                candidate_name = 'Selman Dedeakayoğulları'

                # Guardrail to ensure a report exists to be downloaded
                if not report_content:
                    return {
                        "success": False,
                        "message": "I couldn't find a report to generate a PDF from. Please run a new analysis first."
                    }

                # Get language from last report metadata or default
                language = st.session_state.get("last_report_language", "en")

                pdf_bytes = self.pdf_generator.generate_pdf(
                    report_content, job_title, candidate_name, language, company_name
                )

                st.session_state.pdf_data = pdf_bytes
                st.session_state.pdf_filename = f"job_compatibility_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

                return {
                    "success": True,
                    "message": "PDF report generated successfully",
                    "data": {
                        "pdf_size": len(pdf_bytes),
                        "filename": st.session_state.pdf_filename
                    }
                }

            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error generating PDF: {str(e)}"
                }

        elif tool_name == "analyze_job_compatibility":
            try:
                if not self.job_compatibility_analyzer:
                    return {
                        "success": False,
                        "message": "Job compatibility analyzer not initialized"
                    }

                job_description = tool_args.get('job_description', '')
                if not job_description:
                    return {
                        "success": False,
                        "message": "Job description is required"
                    }

                # Get report language from tool args (required parameter)
                report_language = tool_args.get('report_language', 'en')
                company_name = tool_args.get('company_name')

                # Validate language
                if report_language not in ['en', 'tr']:
                    report_language = 'en'  # Default to English if invalid

                # Generate compatibility report with specified language
                report_data = self.job_compatibility_analyzer.generate_compatibility_report(
                    job_description, report_language, company_name
                )

                if "error" in report_data:
                    return {"success": False, "message": report_data["error"]}

                # Store report data in session state for PDF generation
                st.session_state.last_compatibility_report = report_data["report_text"]
                st.session_state.last_job_title = report_data["job_title"]
                st.session_state.last_company_name = report_data["company_name"]
                st.session_state.last_report_language = report_language

                return {
                    "success": True,
                    "message": "Job compatibility analysis completed",
                    "data": {
                        "report": report_data["report_text"],
                        "job_title": report_data["job_title"],
                        "company_name": report_data["company_name"],
                        "compatibility_score": report_data.get("compatibility_score", 0),
                        "language": report_language
                    }
                }

            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error analyzing job compatibility: {str(e)}"
                }

        else:
            return {
                "success": False,
                "message": f"Unknown tool: {tool_name}"
            }