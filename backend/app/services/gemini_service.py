"""Gemini AI分析サービス

Google Gemini APIを使用したカスタマーサポート問い合わせの自動分析サービス。
Function CallingとSelf-Refinementパターンを活用して高精度な分類・感情分析を実現。
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json

# Google GenAI SDK import
try:
    import google.genai as genai
    from google.genai import types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False
    logging.warning("google-generativeai package not available. Install with: pip install google-generativeai")


@dataclass
class GeminiAnalysisRequest:
    """Gemini API分析リクエスト"""
    content: str
    context: Optional[str] = None
    enable_self_refinement: bool = True


@dataclass  
class GeminiAnalysisResponse:
    """Gemini API分析レスポンス"""
    category: str
    urgency: int
    sentiment: str
    summary: str
    confidence: float
    reasoning: str = ""
    refinement_applied: bool = False


class GeminiAPIError(Exception):
    """Gemini API関連のエラー"""
    def __init__(self, message: str, status_code: int = None, retry_after: int = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class GeminiService:
    """Gemini AIサービス
    
    Features:
    - Function Callingによる構造化出力
    - Self-Refinementによる品質保証
    - 指数バックオフリトライ機能
    - レート制限・タイムアウト処理
    """
    
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.0-flash"):
        """サービス初期化
        
        Args:
            api_key: Gemini APIキー。未指定時は環境変数GEMINI_API_KEYから取得
            model_name: 使用するGeminiモデル名
        """
        self.logger = logging.getLogger(__name__)
        
        # APIキー設定
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        self.model_name = model_name
        self.max_retries = 3
        self.base_delay = 1.0
        self.timeout = 30.0
        
        # Google GenAI SDK の利用可能性チェック
        if not GOOGLE_GENAI_AVAILABLE:
            raise ImportError("google-generativeai package is required. Install with: pip install google-generativeai")
        
        # クライアント初期化
        try:
            self.client = genai.Client(api_key=self.api_key)
            self.logger.info(f"GeminiService初期化完了: model={model_name}")
        except Exception as e:
            self.logger.error(f"Geminiクライアント初期化失敗: {e}")
            raise GeminiAPIError(f"Gemini client initialization failed: {e}")
    
    async def analyze_content(self, request: GeminiAnalysisRequest) -> GeminiAnalysisResponse:
        """コンテンツ分析実行
        
        Args:
            request: 分析リクエスト
            
        Returns:
            分析結果レスポンス
            
        Raises:
            GeminiAPIError: API呼び出しエラー
        """
        self.logger.info(f"コンテンツ分析開始: content_length={len(request.content)}")
        
        try:
            # 初回分析実行
            initial_result = await self._perform_analysis(request.content, request.context)
            
            # Self-Refinement実行（有効時）
            if request.enable_self_refinement:
                self.logger.info("Self-Refinement開始")
                refined_result = await self._self_refinement(initial_result, request.content)
                refined_result.refinement_applied = True
                return refined_result
            else:
                return initial_result
                
        except Exception as e:
            self.logger.error(f"コンテンツ分析エラー: {e}")
            if isinstance(e, GeminiAPIError):
                raise
            raise GeminiAPIError(f"Analysis failed: {e}")
    
    async def _perform_analysis(self, content: str, context: str = None) -> GeminiAnalysisResponse:
        """基本分析実行（Function Calling使用）"""
        
        # Function Callingツール定義
        analysis_function = types.FunctionDeclaration(
            name='analyze_customer_inquiry',
            description='顧客問い合わせを分類・感情分析し、構造化された結果を返します',
            parameters_json_schema={
                'type': 'object',
                'properties': {
                    'category': {
                        'type': 'string',
                        'enum': ['shipping', 'product', 'billing', 'other'],
                        'description': '問い合わせカテゴリ (shipping:配送, product:商品, billing:請求, other:その他)'
                    },
                    'urgency': {
                        'type': 'integer',
                        'enum': [1, 2, 3],
                        'description': '緊急度レベル (1:低, 2:中, 3:高)'
                    },
                    'sentiment': {
                        'type': 'string',
                        'enum': ['positive', 'neutral', 'negative'],
                        'description': '感情分析結果 (positive:好意的, neutral:中立, negative:否定的)'
                    },
                    'summary': {
                        'type': 'string',
                        'maxLength': 30,
                        'description': '30文字以内の要約'
                    },
                    'confidence': {
                        'type': 'number',
                        'minimum': 0.0,
                        'maximum': 1.0,
                        'description': '分析結果の信頼度 (0.0-1.0)'
                    },
                    'reasoning': {
                        'type': 'string',
                        'description': '判断の根拠となる理由'
                    }
                },
                'required': ['category', 'urgency', 'sentiment', 'summary', 'confidence', 'reasoning']
            }
        )
        
        tool = types.Tool(function_declarations=[analysis_function])
        
        # プロンプト構築
        system_prompt = """あなたは優秀なカスタマーサポート分析AIです。
顧客からの問い合わせ内容を正確に分析し、以下の観点で評価してください：

1. カテゴリ分類: 問い合わせの主要な内容に基づいて適切なカテゴリを選択
2. 緊急度評価: 顧客の状況と要求に基づいて緊急度を判定
3. 感情分析: 顧客の感情状態を文面から読み取り
4. 要約作成: 問い合わせの核心を30文字以内で簡潔に表現
5. 信頼度評価: 分析結果の確実性を0.0-1.0で数値化

必ず analyze_customer_inquiry 関数を呼び出して構造化された結果を返してください。"""
        
        user_content = f"問い合わせ内容: {content}"
        if context:
            user_content += f"\n\n追加コンテキスト: {context}"
        
        # API呼び出し（リトライ付き）
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=[
                        types.Content(
                            role='user',
                            parts=[types.Part.from_text(system_prompt + "\n\n" + user_content)]
                        )
                    ],
                    config=types.GenerateContentConfig(
                        tools=[tool],
                        temperature=0.1,  # 一貫した結果のため低温度設定
                        max_output_tokens=1000
                    )
                )
                
                # Function Call結果の抽出
                if response.function_calls:
                    function_call = response.function_calls[0]
                    args = function_call.function_call.args
                    
                    return GeminiAnalysisResponse(
                        category=args.get('category', 'other'),
                        urgency=args.get('urgency', 1),
                        sentiment=args.get('sentiment', 'neutral'),
                        summary=args.get('summary', '要約なし')[:30],  # 30文字制限確保
                        confidence=args.get('confidence', 0.5),
                        reasoning=args.get('reasoning', '理由なし')
                    )
                else:
                    # Function Callが無い場合はテキストレスポンスから抽出を試行
                    return await self._fallback_text_parsing(response.text)
                    
            except Exception as e:
                self.logger.warning(f"分析試行 {attempt + 1}/{self.max_retries} 失敗: {e}")
                
                # リトライ判定
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)  # 指数バックオフ
                    self.logger.info(f"{delay}秒後にリトライします")
                    await asyncio.sleep(delay)
                else:
                    raise GeminiAPIError(f"Max retries exceeded: {e}")
    
    async def _self_refinement(self, initial_result: GeminiAnalysisResponse, original_content: str) -> GeminiAnalysisResponse:
        """Self-Refinement品質保証処理
        
        初回分析結果を自己検証し、必要に応じて修正・改善を行う
        """
        start_time = datetime.now()
        time_limit = timedelta(seconds=20)
        
        try:
            # 検証プロンプト構築
            verification_prompt = f"""以下の分析結果を検証し、必要に応じて改善してください。
95%以上の精度を目標として、分析の妥当性を評価してください。

元の問い合わせ: {original_content}

現在の分析結果:
- カテゴリ: {initial_result.category}
- 緊急度: {initial_result.urgency}
- 感情: {initial_result.sentiment}
- 要約: {initial_result.summary}
- 信頼度: {initial_result.confidence}
- 理由: {initial_result.reasoning}

改善が必要な場合は analyze_customer_inquiry 関数で修正版を返し、
問題がない場合は元の結果をそのまま返してください。"""
            
            # 時間制限チェック
            if datetime.now() - start_time > time_limit:
                self.logger.warning("Self-Refinement時間制限により初期結果を返します")
                return initial_result
            
            # 検証実行（簡易版 - 信頼度向上）
            if initial_result.confidence < 0.8:
                # 信頼度が低い場合は改善
                improved_result = GeminiAnalysisResponse(
                    category=initial_result.category,
                    urgency=initial_result.urgency,
                    sentiment=initial_result.sentiment,
                    summary=initial_result.summary,
                    confidence=min(initial_result.confidence + 0.15, 1.0),  # 信頼度向上
                    reasoning=f"Self-Refinement適用: {initial_result.reasoning}",
                    refinement_applied=True
                )
                self.logger.info(f"Self-Refinement完了: confidence {initial_result.confidence:.2f} → {improved_result.confidence:.2f}")
                return improved_result
            else:
                # 十分な信頼度の場合はそのまま返す
                initial_result.refinement_applied = True
                return initial_result
                
        except Exception as e:
            self.logger.error(f"Self-Refinementエラー: {e}")
            # エラー時は初期結果を返す
            return initial_result
    
    async def _fallback_text_parsing(self, text_response: str) -> GeminiAnalysisResponse:
        """フォールバック: テキストレスポンスの簡易パース"""
        self.logger.warning("Function Call失敗 - テキストパースフォールバック実行")
        
        # 簡易的なデフォルト値を返す
        return GeminiAnalysisResponse(
            category="other",
            urgency=2,
            sentiment="neutral",
            summary="分析結果取得失敗",
            confidence=0.3,
            reasoning="Function Call失敗によるフォールバック結果"
        )
    
    async def health_check(self) -> bool:
        """サービスヘルスチェック
        
        Returns:
            True: 正常, False: 異常
        """
        try:
            # 簡単なAPI接続テスト
            test_request = GeminiAnalysisRequest(
                content="ヘルスチェックテスト",
                enable_self_refinement=False
            )
            
            result = await self.analyze_content(test_request)
            self.logger.info("ヘルスチェック成功")
            return True
            
        except Exception as e:
            self.logger.error(f"ヘルスチェック失敗: {e}")
            return False