from flask import jsonify, current_app # current_app をロギングに使う可能性を考慮

def api_error_response(message, status_code=400):
    """
    標準的なAPIエラーレスポンスを生成します。
    Args:
        message (str): クライアントに表示するエラーメッセージ。
        status_code (int): HTTPステータスコード。
    Returns:
        Response: FlaskのJSONレスポンスオブジェクト。
    """
    # サーバー側のエラー(500番台)の場合、ユーザーには汎用的なメッセージを返し、
    # 詳細はログに出力するなどの配慮もここで一元的に行うことができる。
    # 例:
    # if status_code >= 500:
    # current_app.logger.error(f"API Error (Status {status_code}): {message}") # 詳細なエラーはログへ
    #     user_message = "サーバー内部でエラーが発生しました。しばらくしてから再度お試しください。"
    # else:
    #     user_message = message
    # return jsonify({"error": user_message}), status_code

    # シンプルにそのままメッセージを返す場合:
    return jsonify({"error": message}), status_code

def api_success_response(data, status_code=200):
    """
    標準的なAPI成功レスポンスを生成します。
    Args:
        data (dict or any): クライアントに返すデータ。
        status_code (int): HTTPステータスコード。
    Returns:
        Response: FlaskのJSONレスポンスオブジェクト。
    """
    # data が辞書でない場合は、キー 'data' に格納するなどの工夫も可能です。
    # 例:
    # if not isinstance(data, dict):
    #     response_data = {"data": data}
    # else:
    #     response_data = data
    # return jsonify(response_data), status_code

    # シンプルにそのままデータを返す場合:
    return jsonify(data), status_code