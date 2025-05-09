# config.py
import os

class Config:
    """基本的な設定クラス"""
    # Flask自体の設定
    # SECRET_KEY は Replit の Secrets で設定することを強く推奨
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') # Secretsに設定されていなければNoneになる
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 接続プール設定を追加
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,  # 例: 280秒 (多くのDBのデフォルトタイムアウト5分=300秒より少し短く)
        'pool_pre_ping': True # 接続取得前にpingを実行
    }
    
    # アプリケーションのディレクトリ構造に関する設定
    UPLOAD_FOLDER = 'uploads'
    PRESET_FOLDER = 'presets'
    STATIC_AUDIO_FOLDER = os.path.join('static', 'audio') # static/audio へのパス

    # ファイルアップロードの制限
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25MB

    # APIキー (ReplitのSecretsで設定)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_SUCCESS_URL = os.environ.get('STRIPE_SUCCESS_URL', 'http://localhost:5000/payment-success') # 適切なURLに変更
    STRIPE_CANCEL_URL = os.environ.get('STRIPE_CANCEL_URL', 'http://localhost:5000/payment-cancel')   # 適切なURLに変更
    STRIPE_CUSTOMER_PORTAL_RETURN_URL = os.environ.get('STRIPE_CUSTOMER_PORTAL_RETURN_URL', 'http://localhost:5000/account') # 適切なURLに変更
    # データベース設定 (ReplitのSecretsでDATABASE_URLを設定)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///data.db' # Secrets未設定時のフォールバック(開発用)

    # ログファイル (JSONベースのログを使用している場合)
    LOG_FILE = 'preset_log.json'

    #トライアル
    TRIAL_PERIOD_DAYS = 7  # 新規ユーザーのトライアル日数
    TRIAL_API_CALL_LIMIT = 50 # トライアル中のAPIコール上限
    
    # シャドウイング機能関連の定数
    WARMUP_TRANSCRIPT = "5, 4, 3, 2, 1, 0"
    # WARMUP_AUDIO_PATH は static/audio フォルダ内のファイル名を指定
    WARMUP_AUDIO_FILENAME = 'warm-up.mp3' # config.pyでファイル名だけ定義
                                       # app.py で url_for や os.path.join でフルパスを生成

    # チャンク処理関連の定数
    TARGET_CHUNK_SIZE_MB = 20
    TARGET_CHUNK_SIZE_BYTES = TARGET_CHUNK_SIZE_MB * 1024 * 1024
    CHUNK_OVERLAP_MS = 5000  # ミリ秒
    TARGET_CHUNK_DURATION_MS = 10 * 60 * 1000  # 10分 (ミリ秒)

    @staticmethod
    def init_app(app):
        # アプリケーション初期化時に設定に基づいた処理を行う場合 (例: UPLOAD_FOLDERの作成)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        # 必要であれば STATIC_AUDIO_FOLDER も作成
        static_audio_path = os.path.join(app.root_path, app.config['STATIC_AUDIO_FOLDER'])
        os.makedirs(static_audio_path, exist_ok=True)

class DevelopmentConfig(Config):
    """開発環境用の設定 (Replit上での開発時)"""
    DEBUG = True
    # SQLALCHEMY_DATABASE_URI は Config クラスのものを利用するか、
    # Secretsで DEV_DATABASE_URL を別途設定してそれを参照しても良い
    SQLALCHEMY_ECHO = False # Trueにすると実行SQLがコンソールに出力される（デバッグ用）
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600, # SQLiteなら長めでも良いかも
        'pool_pre_ping': True
    }
class ProductionConfig(Config):
    """本番環境用の設定 (Replitでデプロイ時)"""
    DEBUG = False
    # SQLALCHEMY_DATABASE_URI は Secrets の DATABASE_URL を確実に使用
    # その他、本番環境で必要なセキュリティ設定やログ設定など
    # 本番ではプール設定が特に重要
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True
        # 'pool_size': 10, # 必要に応じてプールの最大接続数なども調整
        # 'max_overflow': 20
    }
    
# 使用する設定を辞書で管理
config_by_name = dict(
    dev=DevelopmentConfig,
    prod=ProductionConfig
)

