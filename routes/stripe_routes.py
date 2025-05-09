# routes/stripe_routes.py
import stripe
from flask import Blueprint, request, jsonify, redirect, current_app
from datetime import datetime, timedelta, timezone # timezoneを追加
from models import db, User, SubscriptionProduct # models.py からインポート
from core.auth import auth_required
from core.responses import api_success_response, api_error_response

stripe_bp = Blueprint('stripe', __name__, url_prefix='/api/stripe') # URLプレフィックスを/api/stripeに

@stripe_bp.before_request
def initialize_stripe_api_key():
    # Initialize Stripe API key from app config if not already set
    if not stripe.api_key:
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        current_app.logger.critical("STRIPE_SECRET_KEY is not configured. Stripe functionality will not work.")
        # Potentially raise an error or return a 503 Service Unavailable if critical

# --- Helper Functions (前回と同様) ---
def get_or_create_user(replit_user_id):
    user = User.query.filter_by(replit_user_id=replit_user_id).first()
    if not user:
        user = User(replit_user_id=replit_user_id)
        # 新規ユーザーにトライアルを付与 (例: 7日間、APIコール50回)
        user.is_trial_period_active = True
        user.trial_expires_at = datetime.now(timezone.utc) + timedelta(days=current_app.config.get('TRIAL_PERIOD_DAYS', 7))
        user.trial_api_call_limit = current_app.config.get('TRIAL_API_CALL_LIMIT', 50)
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(f"New user created with trial: {replit_user_id}")
    return user

# --- API Endpoints (前回提案したものを移植・調整) ---

@stripe_bp.route('/products', methods=['GET'])
@auth_required
def list_products():
    """提供中の課金プラン一覧を返す"""
    try:
        products = SubscriptionProduct.query.filter_by(is_active=True).order_by(SubscriptionProduct.price_amount).all()
        return api_success_response([
            {
                "id": p.id, # DBのID
                "stripe_price_id": p.stripe_price_id,
                "name": p.name,
                "description": p.description,
                "price_amount": p.price_amount, # セント単位
                "currency": p.currency,
                "plan_type": p.plan_type, # 'subscription' or 'one_time'
                "api_call_limit": p.api_call_limit,
                "duration_hours": p.duration_hours # ワンタイムプランの有効期間
            } for p in products
        ])
    except Exception as e:
        current_app.logger.error(f"Error fetching products: {e}", exc_info=True)
        return api_error_response("商品リストの取得中にエラーが発生しました。", 500)


@stripe_bp.route('/create-checkout-session', methods=['POST'])
@auth_required
def create_checkout_session():
    replit_user_id = request.headers.get('X-Replit-User-Id')
    data = request.json
    # フロントエンドからは、StripeのPrice ID (stripe_price_id) を受け取ることを想定
    stripe_price_id = data.get('stripePriceId')

    if not stripe_price_id:
        return api_error_response("価格ID (stripePriceId) が必要です。", 400)

    product_info = SubscriptionProduct.query.filter_by(stripe_price_id=stripe_price_id, is_active=True).first()
    if not product_info:
        return api_error_response("無効または利用できない価格IDです。", 400)

    user = get_or_create_user(replit_user_id) # ユーザー取得またはトライアル付きで作成
    stripe_customer_id = user.stripe_customer_id

    if not stripe_customer_id:
        try:
            customer_params = {'name': request.headers.get('X-Replit-User-Name'),
                               'metadata': {'replit_user_id': replit_user_id}}
            # Replitからメールアドレスが取得可能であれば追加
            # user_email = request.headers.get('X-Replit-User-Email')
            # if user_email:
            # customer_params['email'] = user_email
            customer = stripe.Customer.create(**customer_params)
            stripe_customer_id = customer.id
            user.stripe_customer_id = stripe_customer_id
            db.session.commit()
            current_app.logger.info(f"Stripe customer created: {stripe_customer_id} for Replit user {replit_user_id}")
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe顧客作成エラー for {replit_user_id}: {e}", exc_info=True)
            return api_error_response(f"決済サービスの顧客情報作成に失敗しました: {e.user_message or str(e)}", 500)
        except Exception as e: # その他の予期せぬエラー
            current_app.logger.error(f"予期せぬエラー（Stripe顧客作成時）for {replit_user_id}: {e}", exc_info=True)
            return api_error_response("顧客情報の作成中に予期せぬエラーが発生しました。", 500)


    try:
        # 支払い成功時・キャンセル時のリダイレクト先URLをconfigから取得
        success_url = current_app.config.get('STRIPE_SUCCESS_URL')
        cancel_url = current_app.config.get('STRIPE_CANCEL_URL')
        if not success_url or not cancel_url:
            current_app.logger.error("Stripe Success/Cancel URLがconfigに設定されていません。")
            return api_error_response("サーバー設定エラー（リダイレクトURL）", 500)

        checkout_session_params = {
            'customer': stripe_customer_id,
            'payment_method_types': ['card'], # 必要に応じて他の支払い方法を追加
            'line_items': [{'price': stripe_price_id, 'quantity': 1}],
            'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}', # セッションIDを渡す
            'cancel_url': cancel_url,
            'metadata': { # Webhookで利用
                'replit_user_id': replit_user_id,
                'db_product_id': product_info.id # DBのSubscriptionProduct.idも渡す
            }
        }

        if product_info.plan_type == 'subscription':
            checkout_session_params['mode'] = 'subscription'
            # サブスクリプションにトライアルを適用する場合のロジック
            # (Stripe側でトライアルを設定するか、アプリ側で管理するかによる)
            # 例: Stripeの既存顧客でなければトライアルを適用
            # is_new_customer_for_subscription = not user.current_subscription_id
            # if is_new_customer_for_subscription and current_app.config.get('STRIPE_SUBSCRIPTION_TRIAL_DAYS', 0) > 0 :
            #     checkout_session_params['subscription_data'] = {
            #         'trial_period_days': current_app.config.get('STRIPE_SUBSCRIPTION_TRIAL_DAYS')
            #     }
        else: # 'one_time'
            checkout_session_params['mode'] = 'payment'

        checkout_session = stripe.checkout.Session.create(**checkout_session_params)
        current_app.logger.info(f"Stripe Checkout session created: {checkout_session.id} for user {replit_user_id}, price {stripe_price_id}")
        # フロントエンドには checkout_session.url を返してリダイレクトさせる
        return api_success_response({'checkoutUrl': checkout_session.url, 'sessionId': checkout_session.id})

    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe Checkoutセッション作成エラー (User: {replit_user_id}, Price: {stripe_price_id}): {e}", exc_info=True)
        return api_error_response(f"決済セッションの作成に失敗しました: {e.user_message or str(e)}", getattr(e, 'http_status', 500))
    except Exception as e:
        current_app.logger.error(f"予期せぬエラー（Checkoutセッション作成時 - User: {replit_user_id}, Price: {stripe_price_id}）: {e}", exc_info=True)
        return api_error_response("決済セッションの作成中に予期せぬエラーが発生しました。", 500)

@stripe_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    event = None

    if not webhook_secret:
        current_app.logger.error("Stripe Webhookシークレットが設定されていません。")
        return api_error_response("サーバー設定エラー（Webhookシークレット）", 500) # 500 Internal Server Error

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        current_app.logger.info(f"Webhook受信: Event ID {event.id}, Type {event.type}")
    except ValueError as e: # Invalid payload
        current_app.logger.error(f"Stripe Webhookペイロード検証エラー: {e}", exc_info=True)
        return api_error_response("無効なペイロードです。", 400)
    except stripe.error.SignatureVerificationError as e: # Invalid signature
        current_app.logger.error(f"Stripe Webhook署名検証エラー: {e}", exc_info=True)
        return api_error_response("無効な署名です。", 400)
    except Exception as e:
        current_app.logger.error(f"Stripe Webhookイベント構築エラー: {e}", exc_info=True)
        return api_error_response("Webhookイベントの処理中にエラーが発生しました。", 500)


    # --- イベント処理 ---
    # checkout.session.completed イベントでユーザーのプラン情報を更新
    if event.type == 'checkout.session.completed':
        session = event.data.object # CheckoutSessionオブジェクト
        replit_user_id = session.metadata.get('replit_user_id')
        db_product_id = session.metadata.get('db_product_id') # DBのSubscriptionProduct.id

        if not replit_user_id or not db_product_id:
            current_app.logger.error(f"Webhook (checkout.session.completed): metadataにreplit_user_idまたはdb_product_idがありません。Session ID: {session.id}")
            return api_error_response("必要なメタデータが不足しています。", 400)

        user = User.query.filter_by(replit_user_id=replit_user_id).first()
        product_info = SubscriptionProduct.query.get(db_product_id) # DBのIDで検索

        if not user:
            current_app.logger.error(f"Webhook (checkout.session.completed): Userが見つかりません。ReplitUserID: {replit_user_id}, Session ID: {session.id}")
            return api_error_response("ユーザー情報が見つかりません。", 404)
        if not product_info:
            current_app.logger.error(f"Webhook (checkout.session.completed): Productが見つかりません。DB Product ID: {db_product_id}, Session ID: {session.id}")
            return api_error_response("商品情報が見つかりません。", 404)

        try:
            if product_info.plan_type == 'subscription':
                stripe_subscription_id = session.get('subscription')
                if not stripe_subscription_id:
                    current_app.logger.error(f"Webhook (checkout.session.completed): subscription IDが取得できませんでした。Session ID: {session.id}")
                    return api_error_response("サブスクリプション情報が取得できませんでした。", 500)

                # Stripeから最新のSubscription情報を取得
                stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)

                user.current_subscription_id = stripe_sub.id
                user.subscription_status = stripe_sub.status # 'active', 'trialing', etc.
                user.subscription_current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)
                user.api_calls_monthly_limit = product_info.api_call_limit or 0
                user.api_calls_monthly_used = 0 # 新規または更新なのでリセット
                user.api_calls_reset_date = user.subscription_current_period_end

                # 購入時にトライアル状態を解除（アプリ側のトライアルをStripeトライアルと別に管理する場合）
                user.is_trial_period_active = False
                user.trial_expires_at = None
                user.trial_api_call_used = 0

                current_app.logger.info(f"サブスクリプション '{product_info.name}' 開始/更新 for User {user.replit_user_id}. Stripe Sub ID: {stripe_sub.id}, Status: {stripe_sub.status}")

            elif product_info.plan_type == 'one_time':
                now_utc = datetime.now(timezone.utc)
                # 既存の有効期限が未来の場合、そこから延長。そうでなければ現在時刻から延長。
                current_expiry = user.onetime_access_expires_at if user.onetime_access_expires_at and user.onetime_access_expires_at > now_utc else now_utc
                user.onetime_access_expires_at = current_expiry + timedelta(hours=product_info.duration_hours or 0)

                # APIコール数の加算（既存の残りがあればそれに加算）
                existing_onetime_remaining = (user.api_calls_onetime_limit - user.api_calls_onetime_used) if user.api_calls_onetime_limit > user.api_calls_onetime_used else 0
                user.api_calls_onetime_limit = existing_onetime_remaining + (product_info.api_call_limit or 0)
                user.api_calls_onetime_used = 0 # 新規購入分はリセット

                # 購入時にトライアル状態を解除
                user.is_trial_period_active = False
                user.trial_expires_at = None
                user.trial_api_call_used = 0

                current_app.logger.info(f"ワンタイムアクセス '{product_info.name}' 購入 for User {user.replit_user_id}. Expires at: {user.onetime_access_expires_at}")

            user.updated_at = datetime.now(timezone.utc)
            db.session.commit()

        except stripe.error.StripeError as e:
            current_app.logger.error(f"Webhook (checkout.session.completed) Stripe APIエラー: {e}", exc_info=True)
            # DBロールバックは不要（コミット前なので）
            return api_error_response(f"決済情報の処理中にStripe APIエラーが発生しました: {e.user_message or str(e)}", getattr(e, 'http_status', 500))
        except Exception as e: # SQLAlchemyErrorなども含む
            current_app.logger.error(f"Webhook (checkout.session.completed) データベース更新エラー: {e}", exc_info=True)
            db.session.rollback()
            return api_error_response("決済情報のデータベース更新中にエラーが発生しました。", 500)

    # customer.subscription.updated: サブスクリプションのステータス変更（キャンセル、支払い失敗後の再開など）
    elif event.type == 'customer.subscription.updated' or event.type == 'customer.subscription.deleted':
        stripe_sub = event.data.object # Subscriptionオブジェクト
        stripe_customer_id = stripe_sub.customer
        user = User.query.filter_by(stripe_customer_id=stripe_customer_id, current_subscription_id=stripe_sub.id).first()

        if user:
            try:
                user.subscription_status = stripe_sub.status
                user.subscription_current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)
                if stripe_sub.status != 'active': # アクティブでなくなった場合
                    # APIコール数をリセットするかどうかはポリシーによる
                    # user.api_calls_monthly_used = user.api_calls_monthly_limit # 例: 使えなくする
                    pass
                else: # activeに復帰した場合など
                    user.api_calls_reset_date = user.subscription_current_period_end
                    # プラン変更でAPI上限が変わる可能性もあるため、StripeのSubscription ItemからPrice IDを取得し、
                    # DBのSubscriptionProductを引いてapi_call_limitを再設定するのが堅牢
                    # ここでは簡略化のため、既存のlimitを維持する
                    # user.api_calls_monthly_used = 0 # 期間開始時にリセットされているはずだが念のため

                user.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                current_app.logger.info(f"サブスクリプション更新 (Event: {event.type}): User {user.replit_user_id}, Stripe Sub ID {stripe_sub.id}, New Status {stripe_sub.status}")
            except Exception as e:
                current_app.logger.error(f"Webhook (customer.subscription.*) データベース更新エラー: {e}", exc_info=True)
                db.session.rollback()
                # Webhookは200を返さないとStripeがリトライするため、ここでは500を返すが、
                # 永続的なエラーの場合は調査が必要
                return api_error_response("サブスクリプション更新情報のデータベース処理中にエラーが発生しました。", 500)
        else:
            current_app.logger.warning(f"Webhook (customer.subscription.*): UserまたはSubscriptionが見つかりません。Stripe Customer ID: {stripe_customer_id}, Stripe Sub ID: {stripe_sub.id}")


    # 他の重要なイベントタイプ（invoice.payment_succeeded, invoice.payment_failedなど）も同様に処理
    # invoice.payment_succeeded: サブスクリプションの継続支払い成功時。api_calls_monthly_used をリセットするタイミング。
    #                          subscription_current_period_end も更新される。
    elif event.type == 'invoice.payment_succeeded':
        invoice = event.data.object
        stripe_subscription_id = invoice.get('subscription')
        stripe_customer_id = invoice.get('customer')

        if stripe_subscription_id and stripe_customer_id:
            user = User.query.filter_by(stripe_customer_id=stripe_customer_id, current_subscription_id=stripe_subscription_id).first()
            if user and user.subscription_status == 'active': # アクティブなサブスクリプションの支払い成功
                try:
                    # Stripeから最新のSubscription情報を取得して期間終了日を更新
                    stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                    new_period_end = datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)

                    user.subscription_current_period_end = new_period_end
                    user.api_calls_monthly_used = 0 # 月次支払い成功でリセット
                    user.api_calls_reset_date = new_period_end
                    user.updated_at = datetime.now(timezone.utc)
                    db.session.commit()
                    current_app.logger.info(f"サブスクリプション支払い成功・APIコールリセット: User {user.replit_user_id}, Stripe Sub ID {stripe_subscription_id}, New Period End {new_period_end}")
                except stripe.error.StripeError as e:
                    current_app.logger.error(f"Webhook (invoice.payment_succeeded) Stripe APIエラー: {e}", exc_info=True)
                except Exception as e:
                    current_app.logger.error(f"Webhook (invoice.payment_succeeded) データベース更新エラー: {e}", exc_info=True)
                    db.session.rollback()
            else:
                current_app.logger.warning(f"Webhook (invoice.payment_succeeded): UserまたはアクティブなSubscriptionが見つかりません。Customer: {stripe_customer_id}, Sub: {stripe_subscription_id}")


    return api_success_response({'status': 'received'})


@stripe_bp.route('/customer-portal', methods=['POST']) # GETでも良いが、セッション作成なのでPOSTが一般的
@auth_required
def customer_portal():
    replit_user_id = request.headers.get('X-Replit-User-Id')
    user = User.query.filter_by(replit_user_id=replit_user_id).first()

    if not user or not user.stripe_customer_id:
        current_app.logger.warning(f"Customer portal request for user without Stripe customer ID: {replit_user_id}")
        return api_error_response("Stripeの顧客情報が見つかりません。サポートにお問い合わせください。", 404)

    try:
        return_url = current_app.config.get('STRIPE_CUSTOMER_PORTAL_RETURN_URL')
        if not return_url:
            current_app.logger.error("STRIPE_CUSTOMER_PORTAL_RETURN_URLがconfigに設定されていません。")
            return api_error_response("サーバー設定エラー（ポータルURL）", 500)

        portal_session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )
        current_app.logger.info(f"Stripe Customer Portal session created for user: {replit_user_id}")
        return api_success_response({'portalUrl': portal_session.url})
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe Customer Portalセッション作成エラー for {replit_user_id}: {e}", exc_info=True)
        return api_error_response(f"顧客ポータルの起動に失敗しました: {e.user_message or str(e)}", getattr(e, 'http_status', 500))
    except Exception as e:
        current_app.logger.error(f"予期せぬエラー（Customer Portalセッション作成時 - User: {replit_user_id}）: {e}", exc_info=True)
        return api_error_response("顧客ポータルの起動中に予期せぬエラーが発生しました。", 500)


@stripe_bp.route('/user-status', methods=['GET'])
@auth_required
def get_user_billing_status(): # エンドポイント名を変更して明確化
    replit_user_id = request.headers.get('X-Replit-User-Id')
    user = get_or_create_user(replit_user_id) # これでユーザーがいなければトライアル状態で作成される

    now_utc = datetime.now(timezone.utc)
    limit, used = user.get_active_api_limit_and_used() # このメソッドはDB更新の可能性があるので注意
    # get_active_api_limit_and_used内でDBコミットが発生する場合、このエンドポイントはGETだが副作用を持つことになる。
    # 理想的には、状態取得と状態更新は分離する。ここでは簡便のためそのまま。

    is_subscription_active = user.current_subscription_id and \
                             user.subscription_status == 'active' and \
                             user.subscription_current_period_end and \
                             user.subscription_current_period_end > now_utc

    is_onetime_active = user.onetime_access_expires_at and \
                        user.onetime_access_expires_at > now_utc

    is_trial_truly_active = user.is_trial_period_active and \
                            (user.trial_expires_at is None or user.trial_expires_at > now_utc) and \
                            user.trial_api_call_used < user.trial_api_call_limit


    status_data = {
        "replit_user_id": user.replit_user_id,
        "is_special_free_account": user.is_special_free_account,
        "active_plan_type": None, # 'trial', 'subscription', 'one_time', 'none'
        "api_calls_remaining": 0,
        "plan_expires_at": None, # ISO format
        "manage_subscription_url_available": bool(user.stripe_customer_id and is_subscription_active) # Customer Portalが使えるか
    }

    if user.is_special_free_account:
        status_data["active_plan_type"] = "special_free"
        status_data["api_calls_remaining"] = "unlimited"
    elif is_trial_truly_active:
        status_data["active_plan_type"] = "trial"
        status_data["api_calls_remaining"] = user.trial_api_call_limit - user.trial_api_call_used
        status_data["plan_expires_at"] = user.trial_expires_at.isoformat() if user.trial_expires_at else None
    elif is_subscription_active:
        status_data["active_plan_type"] = "subscription"
        status_data["api_calls_remaining"] = user.api_calls_monthly_limit - user.api_calls_monthly_used
        status_data["plan_expires_at"] = user.subscription_current_period_end.isoformat() if user.subscription_current_period_end else None
    elif is_onetime_active:
        status_data["active_plan_type"] = "one_time"
        status_data["api_calls_remaining"] = user.api_calls_onetime_limit - user.api_calls_onetime_used
        status_data["plan_expires_at"] = user.onetime_access_expires_at.isoformat() if user.onetime_access_expires_at else None
    else:
        status_data["active_plan_type"] = "none"


    # 詳細情報（デバッグや管理画面用、本番フロントではここまで細かく出さないかも）
    status_data["details"] = {
        "trial_status": {
            "is_active_flag": user.is_trial_period_active,
            "expires_at": user.trial_expires_at.isoformat() if user.trial_expires_at else None,
            "limit": user.trial_api_call_limit,
            "used": user.trial_api_call_used,
        },
        "subscription_status": {
            "stripe_subscription_id": user.current_subscription_id,
            "status": user.subscription_status,
            "current_period_end": user.subscription_current_period_end.isoformat() if user.subscription_current_period_end else None,
            "limit": user.api_calls_monthly_limit,
            "used": user.api_calls_monthly_used,
            "reset_date": user.api_calls_reset_date.isoformat() if user.api_calls_reset_date else None,
        },
        "onetime_status": {
            "expires_at": user.onetime_access_expires_at.isoformat() if user.onetime_access_expires_at else None,
            "limit": user.api_calls_onetime_limit,
            "used": user.api_calls_onetime_used,
        }
    }

    return api_success_response(status_data)