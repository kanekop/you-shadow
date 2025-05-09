# models.py
from datetime import datetime, timedelta, timezone # timezone をインポート
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint # CheckConstraint をインポート

db = SQLAlchemy()

class User(db.Model): # ユーザー情報を格納するモデル (新規または既存を拡張)
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    replit_user_id = db.Column(db.String, unique=True, nullable=False, index=True) # ReplitユーザーID
    stripe_customer_id = db.Column(db.String, unique=True, nullable=True, index=True) # Stripe顧客ID

    # 月額サブスクリプション関連
    current_subscription_id = db.Column(db.String, nullable=True, index=True) # 現在アクティブなStripe Subscription ID
    subscription_status = db.Column(db.String, nullable=True) #例: 'active', 'canceled', 'past_due', 'trialing'
    subscription_current_period_end = db.Column(db.DateTime(timezone=True), nullable=True) # サブスクリプションの現在の期間終了日時 (UTC)
    api_calls_monthly_limit = db.Column(db.Integer, default=0) # 月間のAPIコール上限
    api_calls_monthly_used = db.Column(db.Integer, default=0)  # 当月のAPIコール使用数
    api_calls_reset_date = db.Column(db.DateTime(timezone=True), nullable=True) # APIコール数がリセットされる日付 (UTC)

    # ワンタイムオプション関連
    onetime_access_expires_at = db.Column(db.DateTime(timezone=True), nullable=True) # ワンタイムアクセスの有効期限 (UTC)
    api_calls_onetime_limit = db.Column(db.Integer, default=0) # ワンタイム購入でのAPIコール上限
    api_calls_onetime_used = db.Column(db.Integer, default=0) # ワンタイム購入でのAPIコール使用数

    # 無料枠・トライアル関連
    is_trial_period_active = db.Column(db.Boolean, default=False) # 初回トライアル期間中か
    trial_expires_at = db.Column(db.DateTime(timezone=True), nullable=True) # トライアル有効期限 (UTC)
    trial_api_call_limit = db.Column(db.Integer, default=50) # トライアル中のAPIコール上限 (例: 50回)
    trial_api_call_used = db.Column(db.Integer, default=0) # トライアル中のAPIコール使用数

    # 特別無料アカウント
    is_special_free_account = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 関連付け (既存のモデルと必要に応じて)
    # practice_logs = db.relationship('PracticeLog', backref='user', lazy=True) # PracticeLogにuser_idのFKが必要

    def get_active_api_limit_and_used(self):
        """現在有効なAPIコールの上限と使用数を返す"""
        now = datetime.now(timezone.utc)
        if self.is_special_free_account:
            return float('inf'), 0 # 特別無料アカウントは無制限

        if self.is_trial_period_active and (self.trial_expires_at is None or self.trial_expires_at > now):
            return self.trial_api_call_limit, self.trial_api_call_used

        if self.current_subscription_id and self.subscription_status == 'active' and \
           self.subscription_current_period_end and self.subscription_current_period_end > now:
            # APIコール数がリセットされるべきか確認
            if self.api_calls_reset_date and self.api_calls_reset_date <= now:
                self.api_calls_monthly_used = 0
                self.api_calls_reset_date = self.subscription_current_period_end # 次の期間終了日にリセット
                db.session.commit()
            return self.api_calls_monthly_limit, self.api_calls_monthly_used

        if self.onetime_access_expires_at and self.onetime_access_expires_at > now:
            return self.api_calls_onetime_limit, self.api_calls_onetime_used

        return 0, 0 # 有効なプランがない場合

class SubscriptionProduct(db.Model): # Stripeの商品情報を格納 (管理用)
    __tablename__ = 'subscription_products'
    id = db.Column(db.Integer, primary_key=True)
    stripe_product_id = db.Column(db.String, unique=True, nullable=False) # Stripeの商品ID
    stripe_price_id = db.Column(db.String, unique=True, nullable=False)   # Stripeの価格ID
    name = db.Column(db.String, nullable=False) # 例: "月額スタンダードプラン", "24時間アクセスパス"
    description = db.Column(db.Text, nullable=True)
    price_amount = db.Column(db.Integer, nullable=False) # 価格 (例: 500円なら50000セント)
    currency = db.Column(db.String, default='jpy', nullable=False)
    plan_type = db.Column(db.String, nullable=False) # 'subscription' または 'one_time'
    api_call_limit = db.Column(db.Integer, nullable=True) # 月額プランの場合の上限、ワンタイムの場合はその購入での上限
    duration_hours = db.Column(db.Integer, nullable=True) # ワンタイムプランの有効時間 (時間単位)
    is_active = db.Column(db.Boolean, default=True) # このプランが現在提供中か

# (AudioRecording, Material, PracticeLog モデルは既存のものを利用、または必要に応じて User との関連付けを追加)
# 例えば PracticeLog に user_id を追加して User と紐付けるなど。
# class PracticeLog(db.Model):
#     ...
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
#     ...