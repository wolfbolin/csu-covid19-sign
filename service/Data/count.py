# coding=utf-8
import Kit
import json
import pymysql
from flask import abort
from flask import request
from flask import jsonify
from Data import data_blue
from flask import current_app as app


@data_blue.route('/notice', methods=["GET"])
def fetch_notice_info():
    conn = app.mysql_pool.connection()
    notice = Kit.get_key_val(conn, "notice")

    return jsonify({
        "status": "success",
        "message": notice
    })


@data_blue.route('/version', methods=["GET"])
def fetch_version_list():
    conn = app.mysql_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sql = "SELECT * FROM `version`"
    cursor.execute(query=sql)
    version_list = cursor.fetchall()
    for version in version_list:
        version["date"] = Kit.datetime2unix(version["date"])
        version["feature"] = json.loads(version["feature"])
        version["update"] = json.loads(version["update"])
        version["bugfix"] = json.loads(version["bugfix"])

    return jsonify(version_list)


@data_blue.route('/version/<string:version>/action/<string:action>', methods=["POST"])
def user_version_action(version, action):
    if action not in ["love", "like", "star", "hate"]:
        return abort(400)

    conn = app.mysql_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sql = "UPDATE `version` SET `{}` = `{}` + 1 WHERE `version`=%s".format(str(action), str(action))
    cursor.execute(query=sql, args=[version])
    conn.commit()

    if cursor.rowcount > 0:
        return jsonify({
            "status": "success",
            "message": "您的反馈已记录~"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "反馈的数据出错了"
        })


@data_blue.route('/count', methods=["POST"])
def update_count_data():
    # 本地数据校验
    client_ip = request.headers.get("X-Real-IP", "0.0.0.0")
    if client_ip != "127.0.0.1":
        return abort(400, "Reject IP:{}".format(client_ip))

    # 初始化各项数据
    conn = app.mysql_pool.connection()
    date_now = Kit.str_time("%Y-%m-%d")

    # 统计当前在线用户人数
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sql = "SELECT COUNT(*) as user_num FROM `user` WHERE `online`='Yes'"
    cursor.execute(query=sql)
    user_num = int(cursor.fetchone()["user_num"])

    # 统计当日打卡用户位置
    sql = "SELECT * FROM `location` WHERE `date`=%s"
    cursor.execute(query=sql, args=[date_now])
    task_data = cursor.fetchall()

    location_tree = {"name": "*", "child": {}}
    for region in task_data:
        if region["location"] == "Unknown":
            continue

        location = json.loads(region["location"])
        country_child = set_location_count(location, location_tree["child"], "country")
        province_child = set_location_count(location, country_child, "province")
        city_child = set_location_count(location, province_child, "city")
        set_location_count(location, city_child, "district")

    # 更新当日统计数据
    sql = "REPLACE INTO `count`(`date`,`user_num`,`location_tree`) VALUES (%s,%s,%s)"
    cursor.execute(sql, args=[date_now, user_num, json.dumps(location_tree, ensure_ascii=False)])
    conn.commit()

    return "Re-count success"


def set_location_count(location, node, key):
    node.setdefault(location[key], {"name": location[key], "count": 0, "child": {}})
    node[location[key]]["count"] += 1
    return node[location[key]]["child"]


@data_blue.route('/count/location')
def get_location():
    # 获取数据日期
    date = request.args.get("date", Kit.str_time("%Y-%m-%d"))

    conn = app.mysql_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sql = "SELECT * FROM `count` WHERE `date`=%s"
    cursor.execute(sql, args=[date])
    data = cursor.fetchone()
    if data is None:
        return jsonify({
            "status": "success",
            "update_date": date,
            "data": {"中国": {"child": {}}}
        })

    return jsonify({
        "status": "success",
        "update_date": date,
        "data": json.loads(data["location_tree"])
    })


@data_blue.route('/count/user')
def get_user_count():
    conn = app.mysql_pool.connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sql = """
    SELECT
        `date`,
        `user_num` 
    FROM
        `count`
    ORDER BY
        `date` DESC 
        LIMIT 30
    """
    cursor.execute(query=sql)
    user_data = cursor.fetchall()
    user_data_key = []
    user_data_val = []
    for it in user_data:
        user_data_key.append(str(it["date"])[5:])
        user_data_val.append(it["user_num"])

    return jsonify({
        "status": "success",
        "user_data": [user_data_key[::-1], user_data_val[::-1]]
    })
