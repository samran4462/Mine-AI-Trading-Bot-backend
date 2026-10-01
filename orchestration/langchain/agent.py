import os
from dotenv import load_dotenv
load_dotenv()

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from typing import Dict, Any

class LangchainOrchestrator:
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.model = llm_model
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        
        if self.api_key:
            self.llm = ChatOpenAI(temperature=0, model=self.model, api_key=self.api_key, max_retries=1, request_timeout=5)
        else:
            self.llm = None
            
        self.validation_prompt = PromptTemplate(
            input_variables=["htf_context", "ltf_structure", "liquidity", "news_risk", "volatility"],
            template="""
            You are the Strategy Validation Agent for a strict scalping system.
            Review the following market data:
            HTF Context: {htf_context}
            LTF Structure: {ltf_structure}
            Liquidity Status: {liquidity}
            News Risk: {news_risk}
            Volatility: {volatility}
            
            Based on the strict multi-layer methodology, determine if a scalp trade is valid.
            Return exactly 'TRADE' or 'NO TRADE' on the first line.
            On the second line, provide a short 1-sentence reason.
            """
        )

    def evaluate_setup(self, market_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Takes processed feature engineering data and runs the Langchain prompt.
        """
        htf = market_data.get('htf_context', 'neutral')
        ltf = market_data.get('ltf_structure', 'neutral')
        liquidity = market_data.get('liquidity', 'none')
        news_risk = market_data.get('news_risk', 'high')
        
        decision = "NO TRADE"
        reason = "Strict criteria not met."
        api_failed = False
        
        if self.llm:
            try:
                # Execute real AI validation
                prompt_text = self.validation_prompt.format(**market_data)
                response = self.llm.invoke(prompt_text)
                
                # Parse output (Expected format: Line 1: TRADE/NO TRADE, Line 2: Reason)
                lines = response.content.strip().split('\n')
                decision = lines[0].strip() if lines else "NO TRADE"
                reason = lines[1].strip() if len(lines) > 1 else "AI provided no specific reason."
                
                # Cleanup potential markdown/formatting
                decision = "TRADE" if "TRADE" in decision and "NO" not in decision else "NO TRADE"
                
            except Exception as e:
                api_failed = True
                reason = f"API Error (Quota/Connection). Using Fallback Engine."
        else:
            api_failed = True
            reason = "No API Key. Using Fallback Engine."
            
        if api_failed:
            # Multi-Indicator Confluence (Trend + RSI + Volume + Structure)
            if news_risk == "high":
                decision = "NO TRADE"
                reason = "High-impact news blackout active."
            elif ltf == "bullish" and liquidity == "AI_Confluence_Bullish":
                decision = "TRADE"
                reason = f"[AI Master Algoritm] Perfect Bullish Confluence (Trend + Vol + Momentum + RSI)."
            elif ltf == "bearish" and liquidity == "AI_Confluence_Bearish":
                decision = "TRADE"
                reason = f"[AI Master Algoritm] Perfect Bearish Confluence (Trend + Vol + Momentum + RSI)."
            else:
                 decision = "NO TRADE"
                 reason = "Waiting for Perfect AI Confluence (Multiple indicators must align)."
            
        return {
            "decision": decision,
            "reason": reason,
            "model_used": self.model if not api_failed else "fallback_static_logic"
        }
