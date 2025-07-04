from app import app, db # app と db をインポート
from models import SubscriptionProduct # モデルをインポート

# アプリケーションコンテキスト内で実行
with app.app_context():
    # 例: 月額プラン
    monthly_plan = SubscriptionProduct(
        stripe_product_id='prod_SHdduM2lTpzIxx', # Stripeの商品ID
        stripe_price_id='price_1RN4M12eNinyIb3S3MfESCgS', # Stripeの価格ID
        name='月額スタンダードプラン',
        description='基本的な機能が月額で利用できます。',
        price_amount=100000, # 1000円の場合 (セント単位なので1000 * 100)
        currency='jpy',
        plan_type='subscription',
        api_call_limit=1000, # 例: 月1000回
        is_active=True
    )
    db.session.add(monthly_plan)

    # 例: ワンタイムプラン
    onetime_pass = SubscriptionProduct(
        stripe_product_id='prod_SHdehKztmY3IKj',
        stripe_price_id='price_1RN4Nd2eNinyIb3Sc7fmBoBu',
        name='24時間アクセスパス',
        description='24時間、APIを200回まで利用可能です。',
        price_amount=20000, # 200円の場合
        currency='jpy',
        plan_type='one_time',
        api_call_limit=200,
        duration_hours=24,
        is_active=True
    )
    db.session.add(onetime_pass)

    try:
        db.session.commit()
        print("SubscriptionProduct がデータベースに登録されました。")
    except Exception as e:
        db.session.rollback()
        print(f"データベース登録エラー: {e}")