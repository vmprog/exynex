#!/usr/bin/env python3

"""This command line utility allows you to perform static and dynamic
analysis of android apk files.
Project page:
https://github.com/vmprog/exynex/blob/main/README.md
"""

import sys
import os.path
import logging
import subprocess
import argparse
import json
import tempfile
from datetime import datetime
import time
import xmltodict

stdout = sys.stdout

# Configuring the logger object

logger = logging.getLogger('')
if logger.hasHandlers():
    logger.handlers.clear()
logger.setLevel(logging.INFO)
fh = logging.FileHandler('exynex.log')
sh = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] '
    '%(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
fh.setFormatter(formatter)
sh.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(sh)


def check_command_line(path_to_apk, output):
    """Checks the correctness of the command line.

    Args:
      path_to_apk: Absolute path of apk placement.
      output: Absolute path of report placement.

    Returns:
      Nothing.

    Raises:
      SystemExit: If no path to apk  is found.
      OSError: If error creating the report file.
    """

    logger.debug('Entering the function: "check_command_line"')

    check_path_to_apk = os.path.exists(path_to_apk)
    if not check_path_to_apk:
        logger.error('There is no apk on the specified path: %s', path_to_apk)
        raise SystemExit(1)

    try:
        with open(output, 'w+') as output_report:
            output_report.close()
    except OSError as error_rep:
        logger.error('Could not write output (reason: %r): %r',
                     error_rep, output)
        sys.exit(1)

    logger.debug('Exiting the function: "check_command_line"')


def start_jadx(path_to_apk, tempdir):
    """Start JADX decompiler.

    Args:
      path_to_apk: Absolute path of apk placement.
      tempdir: Absolute path for temp files.

    Returns:
      Nothing.

    Raises:
      OSError: If JADX runtime error.
    """

    logger.debug('Entering the function: "start_jadx"')

    jadx_dir = f'{tempdir}/resources'
    if not os.path.exists(jadx_dir):
        jadx = f'./jadx/bin/jadx {path_to_apk} -d {tempdir}'
        logger.info('Starting Jadx: %s', jadx)
        try:
            jadx_output = os.popen(jadx).read()
            logger.debug(jadx_output)
        except OSError as error_jd:
            logger.warning('Jadx runtime error (reason: %r):',
                           error_jd)
            sys.exit(1)

    logger.debug('Exiting the function: "start_jadx"')


def check_device():
    """Checking the device connection.

    Args:
      Nothing.

    Returns:
      Dict with magisk status.

    Raises:
      SystemExit: If the device is not connected.
    """

    logger.debug('Entering the function: "check_device"')

    get_devices = 'adb devices | grep device$'
    ret_val = os.popen(get_devices).read()
    logger.debug(ret_val)
    if not ret_val:
        logger.error('Error checking devices!: %s', ret_val)
        raise SystemExit(1)

    logger.debug('Exiting the function: "check_device"')

    return{'magisk': is_magisk()}


def get_badging(path_to_apk):
    """Get dump from apk with aapt dump badging.

    Args:
      path_to_apk: Absolute path of apk placement.

    Returns:
      Nothing.

    Raises:
      SystemExit: If error getting badging.
      SystemExit: If error getting the package name.
      SystemExit: If error getting the application name.
      SystemExit: If error getting the version.
      SystemExit: If error getting the version_code.
    """

    logger.debug('Entering the function: "get_badging"')

    get_badging_cmd = f'aapt dump badging {path_to_apk}'
    badging = os.popen(get_badging_cmd).read()
    logger.debug(badging)
    if not badging:
        logger.error('Error getting the badging.')
        raise SystemExit(1)

    awk_cmd = 'awk \'/package/{gsub("name=|\'"\'"\'",""); printf $2}\''
    package_cmd = f'echo "{badging}" | {awk_cmd}'
    logger.info('Getting the package name.')
    package = os.popen(package_cmd).read()
    logger.debug(package)
    if not package:
        logger.error('Error getting the package name!')
        raise SystemExit(1)

    cmd = 'grep "application-label:" | sed \'s/^.*://\' | tr -d \'\\n\''
    app_name_cmd = f'echo "{badging}" | {cmd}'
    logger.info('Getting the application name.')
    app_name = os.popen(app_name_cmd).read()
    logger.debug(app_name)
    if not app_name:
        logger.error('Error getting the application name!')
        raise SystemExit(1)

    cmd1 = 'grep "versionName"'
    cmd2 = 'sed -e "s/.*versionName=\'//" -e "s/\' .*//" | tr -d \'\\n\''
    version_cmd = f'echo "{badging}" | {cmd1} | {cmd2}'
    logger.info('Getting the version.')
    version = os.popen(version_cmd).read()
    logger.debug(version)
    if not version:
        logger.error('Error getting the version!')
        raise SystemExit(1)

    cmd1 = 'grep "versionCode"'
    cmd2 = 'sed -e "s/.*versionCode=\'//" -e "s/\' .*//" | tr -d \'\\n\''
    version_code_cmd = f'echo "{badging}" | {cmd1} | {cmd2}'
    logger.info('Getting the version_code.')
    version_code = os.popen(version_code_cmd).read()
    logger.debug(version_code)
    if not version_code:
        logger.error('Error getting the version_code!')
        raise SystemExit(1)

    logger.debug('Exiting the function: "get_badging"')

    return{'package': package, 'app_name': app_name, 'version': version,
           'version_code': version_code}


def get_geo():
    """Get location.

    Args:
      Nothing.

    Returns:
      geo_data: Dictionary with geo data.

    Raises:
      Nothing.
    """

    logger.debug('Entering the function: "get_geo"')

    geo_data = {}
    cmd1 = 'adb shell dumpsys location'
    cmd2 = 'grep -o -m1 \'Location\\[network [0-9]*,[0-9]*\' | head -1'
    cmd3 = 'sed \'s/Location\\[network //\''
    cmd4 = 'tr -d \' \\t\\n\\r\\f\''
    lat_cmd = f'{cmd1} | {cmd2} | {cmd3} | {cmd4}'
    lat = os.popen(lat_cmd).read()
    logger.debug(lat)
    if len(lat):
        geo_data['lat'] = lat
    else:
        geo_data['lat'] = ''
        logger.error('Error getting lat.')

    cmd1 = 'adb shell dumpsys location'
    cmd2 = 'grep -o -m1 \'Location\\[network [0-9,]*\' | head -1'
    cmd3 = 'sed \'s/Location\\[network [0-9]*,[0-9]*,//\''
    cmd4 = 'tr -d \' \\t\\n\\r\\f\''
    lon_cmd = f'{cmd1} | {cmd2} | {cmd3} | {cmd4}'
    lon = os.popen(lon_cmd).read()
    logger.debug(lon)
    if len(lon):
        geo_data['lon'] = lon
    else:
        geo_data['lon'] = ''
        logger.error('Error getting lon.')

    logger.debug('Exiting the function: "get_geo"')
    return geo_data


def perform_static_analysis(badging, tempdir):
    """Main SAST function.

    Args:
      badging: Aapt output.
      output: Absolute path of report placement.
      tempdir: Absolute path for temp files.

    Returns:
      SAST dataset.

    Raises:
      Nothing.
    """
    logger.debug('Entering the function: "perform_static_analysis"')

    manifest_path = '%s/resources/AndroidManifest.xml' % (tempdir)
    with open(manifest_path) as fd:
        manifest = xmltodict.parse(fd.read())

    data = {}

    data['app_name'] = badging['app_name']
    data['package_name'] = manifest['manifest']['@package']
    data['version'] = badging['version']
    data['version_code'] = badging['version_code']

    cmd1 = f'keytool -printcert -file {tempdir}/resources/META-INF/*.*SA'
    cmd2 = 'grep -Po "(SHA1|SHA256:) .*" -m 1'
    cmd3 = 'xxd -r -p | openssl base64'
    cmd4 = 'tr -- \'+/=\' \'-_\' | tr -d \'\\n\''
    checksum_cmd = f'{cmd1} | {cmd2} | {cmd3} | {cmd4}'
    checksum = os.popen(checksum_cmd).read()
    logger.debug(checksum)
    if len(checksum):
        data['checksum'] = checksum
    else:
        logger.error('Error getting checksum.')

    data['analysis'] = []
    device = {}

    cmd1 = 'adb shell getprop | grep product'
    cmd2 = 'sort -u'
    os_build_cmd = f'{cmd1} | {cmd2}'
    os_build = os.popen(os_build_cmd).read()
    logger.debug(os_build)
    if len(os_build):
        device['os_build'] = os_build.split('\n')
    else:
        logger.error('Error getting os_build.')

    cmd1 = 'adb shell settings get secure android_id'
    cmd2 = 'tr -d \'\\n\''
    android_id_cmd = f'{cmd1} | {cmd2}'
    android_id = os.popen(android_id_cmd).read()
    logger.debug(android_id)
    if len(android_id):
        device['android_id'] = android_id
    else:
        logger.error('Error getting android_id.')

    cmd1 = ('adb shell su -c grep adid_key /data/data/com.google.android.gms'
            '/shared_prefs/adid_settings.xml')
    cmd2 = 'grep "<string name=\\"adid_key\\">"'
    cmd3 = 'sed \'s/<string name="adid_key">\\(.*\\)<\\/string>/\\1/\''
    cmd4 = 'awk \'{$1=$1};1\''
    cmd5 = 'tr -d \'\\n\''
    advertising_id_cmd = f'{cmd1} | {cmd2} | {cmd3} | {cmd4} | {cmd5}'
    advertising_id = os.popen(advertising_id_cmd).read()
    logger.debug(advertising_id)
    if len(advertising_id):
        device['advertising_id'] = advertising_id
    else:
        logger.error('Error getting advertising_id.')

    cmd1 = 'adb shell service call iphonesubinfo 1'
    cmd2 = ('awk -F"\'" \'NR>1 { gsub(/\\./,"",$2); imei=imei $2 } '
            'END {printf imei}\'')
    cmd3 = 'tr -d \' \\t\\n\\r\\f\''
    imei_cmd = f'{cmd1} | {cmd2} | {cmd3}'
    imei = os.popen(imei_cmd).read()
    logger.debug(imei)
    if len(imei):
        device['imei'] = imei
    else:
        device['imei'] = ''
        logger.error('Error getting imei.')

    cmd1 = 'adb shell dumpsys account | grep -o -m1 \'Account {name=[^,]*\''
    cmd2 = 'sed \'s/Account {name=//\''
    cmd3 = 'tr -d \' \\t\\n\\r\\f\''
    google_account_cmd = f'{cmd1} | {cmd2} | {cmd3}'
    google_account = os.popen(google_account_cmd).read()
    logger.debug(google_account)
    if len(google_account):
        device['google_account'] = google_account
    else:
        device['google_account'] = ''
        logger.error('Error getting google_account.')

    cmd1 = 'adb shell dumpsys netstats'
    cmd2 = 'grep -E -m1 -o \'iface=wlan.*networkId=\"[^"]*\''
    cmd3 = 'grep -o \'networkId=\".*\' | sed \'s/networkId="//\''
    cmd4 = 'tr -d \' \\t\\n\\r\\f\''
    wifi_ssid_cmd = f'{cmd1} | {cmd2} | {cmd3} | {cmd4}'
    wifi_ssid = os.popen(wifi_ssid_cmd).read()
    logger.debug(wifi_ssid)
    if len(imei):
        device['wifi_ssid'] = wifi_ssid
    else:
        device['wifi_ssid'] = ''
        logger.error('Error getting wifi_ssid.')

    data['analysis'].append({
        'device': device
    })

    static_analysis = {}

    cmd1 = ('grep -r -Eo "(http|https)://[a-zA-Z0-9./?=_%:-]+" '
            f'{tempdir}/sources/')
    cmd2 = 'sort -u'
    urls_cmd = f'{cmd1} | {cmd2}'
    urls = os.popen(urls_cmd).read()
    logger.debug(urls)
    if len(urls):
        static_analysis['urls'] = urls.split('\n')
    else:
        logger.error('Error getting urls.')

    cmd1 = f'grep -r -Po ".*?//\\K.*?(?=/)" {tempdir}/sources/ | sort -u'
    domains_cmd = f'{cmd1}'
    domains = os.popen(domains_cmd).read()
    logger.debug(domains)
    if len(domains):
        static_analysis['domains'] = domains.split('\n')
    else:
        logger.error('Error getting domains.')

    libraries_cmd = f'find {tempdir} -name *.so'
    libraries = os.popen(libraries_cmd).read()
    logger.debug(libraries)
    if len(libraries):
        static_analysis['libraries'] = libraries.split('\n')
    else:
        logger.error('Error getting libraries.')

    cmd1 = f'grep -r "public class" {tempdir}/sources/'
    cmd2 = 'sed \'s/\\(class [^ ]*\\).*/\\1/\''
    classes_cmd = f'{cmd1} | {cmd2}'
    classes = os.popen(classes_cmd).read()
    logger.debug(classes)
    if len(classes):
        static_analysis['classes'] = classes.split('\n')
    else:
        logger.error('Error getting classes.')

    permissions = []
    for item in manifest['manifest']['uses-permission']:
        permissions.append(item['@android:name'])
    static_analysis['permissions'] = permissions

    activities = []
    man_activities = manifest['manifest']['application']['activity']
    if isinstance(man_activities, list):
        for item in man_activities:
            activities.append(item['@android:name'])
    else:
        activities.append(man_activities['@android:name'])
    static_analysis['activities'] = activities

    data['analysis'].append({
        'static_analysis': static_analysis
    })

    logger.debug('Exiting the function: "perform_static_analysis"')

    return data


def get_uid(package):
    """Retrieves the UID of the application user.

    Args:
      package: Package name of apk.

    Returns:
      uid: UID of the application user.

    Raises:
      SystemExit: If error getting the uid.
    """

    logger.debug('Entering the function: "get_uid"')

    get_uid_cmd = (f'adb shell dumpsys package {package} '
                   '| grep -o "userId=\\S*"')
    uid = os.popen(get_uid_cmd).read()
    logger.debug(uid)
    uid = uid[uid.index('=')+1:-1]
    if uid:
        logger.info('The application uid is: %s', uid)
    else:
        logger.error('Error getting the uid!')
        raise SystemExit(1)

    logger.debug('Exiting the function: "get_uid"')

    return uid


def is_magisk():
    """Checking the use of magisk.

    Args:
      Nothing.

    Returns:
      bool: True if magisk used.

    Raises:
      Nothing.
    """

    logger.debug('Entering the function: "is_magisk"')

    get_magisk = 'adb shell pm list packages | grep magisk'
    magisk = os.popen(get_magisk).read()
    logger.debug(magisk)
    logger.debug('Exiting the function: "is_magisk"')

    return bool(magisk)


def set_iptables(uid, magisk, device_ip, su_pass):
    """Configuring iptables for host and device.

    Args:
      uid: Uid of package.
      magisk: Flag for the presence of magisk.
      device_ip: The IP address of the device.
      su_pass: SU password.

    Returns:
      Nothing.

    Raises:
      SystemExit: If device setup error.
      SystemExit: If host setup error.
    """

    logger.debug('Entering the function: "set_iptables"')

    # Setup device / emulator
    if magisk:
        dev_drop = 'adb shell su -c "iptables -P OUTPUT DROP"'
        dev_accept = ('adb shell su -c "iptables -P OUTPUT ACCEPT '
                      f'-m owner --uid-owner {uid}"')
    else:
        dev_drop = 'adb shell "su 0 iptables -P OUTPUT DROP"'
        dev_accept = ('adb shell "su 0 iptables -P OUTPUT ACCEPT '
                      f'-m owner --uid-owner {uid}"')
    ret_drop = os.popen(dev_drop).read()
    logger.debug(ret_drop)
    ret_accept = os.popen(dev_accept).read()
    logger.debug(ret_accept)
    if ret_drop or ret_accept:
        error_str = f'Device setup error! {ret_drop} {ret_accept}'
        logger.error(error_str)
        raise SystemExit(1)

    # Setup host
    if sys.platform == 'linux' or sys.platform == 'linux2':
        ipt1_host = f'echo {su_pass} | sudo -S iptables -t nat -F'
        ret_ipt1 = os.popen(ipt1_host).read()
        logger.debug(ret_ipt1)
        ipt2_host = (f'echo {su_pass} | sudo -S sysctl -w '
                     'net.ipv4.ip_forward=1')
        ret_ipt2 = os.popen(ipt2_host).read()
        logger.debug(ret_ipt2)
        ipt3_host = (f'echo {su_pass} | sudo -S sysctl -w '
                     'net.ipv6.conf.all.forwarding=1')
        ret_ipt3 = os.popen(ipt3_host).read()
        logger.debug(ret_ipt3)
        ipt4_host = (f'echo {su_pass} | sudo -S sysctl -w '
                     'net.ipv4.conf.all.send_redirects=0')
        ret_ipt4 = os.popen(ipt4_host).read()
        logger.debug(ret_ipt4)

        ipt5_host = (f'echo {su_pass} | '
                     f'sudo -S iptables -t nat -A PREROUTING -s {device_ip} '
                     '-p tcp -j REDIRECT --to-port 8080')
        ret_ipt5 = os.popen(ipt5_host).read()
        logger.debug(ret_ipt5)

        if ret_ipt1 or ret_ipt5:
            error_str = f'Host setup error! {ret_ipt1} {ret_ipt5}'
            logger.error(error_str)
            raise SystemExit(1)

    elif sys.platform == 'darwin':
        ipt1_host_mac = (f'echo {su_pass} | sudo -S sysctl -w '
                         'net.inet.ip.forwarding=1')
        ret_ipt1_host_mac = os.popen(ipt1_host_mac).read()
        logger.debug(ret_ipt1_host_mac)

    logger.debug('Exiting the function: "set_iptables"')


def unset_iptables(su_pass, magisk):
    """Unset of the iptables rules on the host and device.

    Args:
      su_pass: SU password.
      magisk: Flag for the presence of magisk.

    Returns:
      Nothing.

    Raises:
      SystemExit: If device iptables unset error.
      SystemExit: If host iptables unset error.
    """

    logger.debug('Entering the function: "unset_iptables"')

    if magisk:
        ipt1_device = 'adb shell su -c "iptables -P OUTPUT ACCEPT"'
        ipt2_device = 'adb shell su -c "iptables -t nat -F"'
    else:
        ipt1_device = 'adb shell "su 0 iptables -P OUTPUT ACCEPT"'
        ipt2_device = 'adb shell "su 0 iptables -t nat -F"'

    ret_accept = os.popen(ipt1_device).read()
    logger.debug(ret_accept)
    ret_nat = os.popen(ipt2_device).read()
    logger.debug(ret_nat)
    if ret_accept or ret_nat:
        err = f'Device iptables unset error: {ret_accept} {ret_nat}!'
        logger.error(err)
        raise SystemExit(1)

    if sys.platform == 'linux' or sys.platform == 'linux2':
        ipt1_host = f'echo {su_pass} | sudo -S iptables -t nat -F'
        ret_nat = os.popen(ipt1_host).read()
        logger.debug(ret_nat)
        if ret_nat:
            logger.error('Host iptables unset error! %ret_nat !', ret_nat)
            raise SystemExit(1)
    # elif sys.platform == 'darwin':

    logger.debug('Exiting the function: "unset_iptables"')


def start_mitm(tempdir):
    """Running mitmdump in transparent mode.

    Args:
      package: Package name of apk.

    Returns:
      process: Mitmdump process.

    Raises:
      SystemExit: If mitmdump startup error.

    """

    logger.debug('Entering the function: "start_mitm"')

    if logger.root.level == logging.DEBUG:
        stdout_mitm = None
    else:
        stdout_mitm = subprocess.PIPE

    start_ts = datetime.timestamp(datetime.now())

    mitm_cmd = ('mitmdump --mode transparent --showhost'
                ' -s har_dump.py'
                f' --set hardump={tempdir}/dump.har'
                f' --set timestamp={start_ts}')

    logger.info('Starting the mitmdump: %r !', mitm_cmd)

    process = subprocess.Popen(mitm_cmd, shell=True,
                               stdout=stdout_mitm,
                               stderr=subprocess.PIPE)

    time.sleep(5)
    retcode = process.returncode
    if bool(retcode):
        logger.error('Mitmdump startup error: %err !', retcode)
        stop_mitm()
        raise SystemExit(1)

    logger.debug('Exiting the function: "start_mitm"')

    return process


def stop_mitm():
    """Stopping mitmdump.

    Args:
      Nothing.

    Returns:
      Nothing.

    Raises:
      Nothing.
    """

    logger.debug('Entering the function: "stop_mitm"')

    # os.system(f'pkill -TERM -P {mitm_process.pid}')
    if sys.platform == 'linux' or sys.platform == 'linux2':
        os.system('pkill -TERM mitmdump')
    elif sys.platform == 'darwin':
        os.system('pkill -f mitmdump')

    logger.debug('Exiting the function: "stop_mitm"')


def perform_dynamic_analysis(data, package, activity_time, device_ip,
                             su_pass, tempdir, magisk):
    """Main DAST function.

    Args:
      package: Package name of apk.
      activity_time: Application activity timer.

    Returns:
      DAST dataset.

    Raises:
      Nothing.
    """

    logger.debug('Entering the function: "perform_dynamic_analysis"')

    uid = get_uid(package)

    set_iptables(uid, magisk, device_ip, su_pass)
    start_mitm(tempdir)
    runtime_data = start_application(package)
    activity(runtime_data['start_timestamp'], activity_time)
    geo = get_geo()
    stop_application(package, runtime_data['pid'])
    stop_mitm()
    unset_iptables(su_pass, magisk)

    # Preparing a data set.
    data['analysis'][0]['device']['geo'] = geo
    dynamic_analysis = {}

    network_activity = []
    try:
        with open(f'{tempdir}/dump.har') as har:
            network_activity = json.load(har)
    except IOError as error_rep:
        logger.error(f'Error reading har.dump {error_rep}')
    finally:
        stop_mitm()

    requested_permissions = []
    dynamic_analysis['network_activity'] = network_activity
    dynamic_analysis['requested_permissions'] = requested_permissions
    data['analysis'].append({
        'dynamic_analysis': dynamic_analysis
    })

    logger.debug('Exiting the function: "perform_dynamic_analysis"')

    return data


def install_apk(package, path_to_apk, magisk):
    """Installing the apk on a device or emulator.

    Args:
      path_to_apk: Absolute path of apk placement.

    Returns:
      Nothing.

    Raises:
      SystemExit: If APK pushing to device/emulator error.
      SystemExit: If APK installation error.
    """

    logger.debug('Entering the function: "install_apk"')

    get_install_status = f'adb shell pm list packages | grep {package}'
    logger.info('Getting package status: %s', get_install_status)
    package_presents = os.popen(get_install_status).read()
    logger.debug(package_presents)
    if not package_presents:
        logger.info('The package %s is not installed.', package)

        # Set SELinux to Permissive mode
        if magisk:
            set_selinux_cmd = 'adb shell su -c "setenforce 0"'
        else:
            set_selinux_cmd = 'adb shell "su 0 setenforce 0"'
        logger.info('Setting SELinux to Permissive mode: %s', set_selinux_cmd)
        set_selinux = os.popen(set_selinux_cmd).read()
        logger.debug(set_selinux_cmd)
        if set_selinux:
            logger.error('Error with set SELinux!: %s', set_selinux)
            raise SystemExit(1)

        # Pushing APK for a silent install
        push_apk_cmd = f'adb push {path_to_apk} /data/local/tmp'
        logger.info('Pushing the APK: %s', push_apk_cmd)
        push_apk = os.popen(push_apk_cmd).read()
        logger.debug(push_apk)
        if 'file pushed' in push_apk:
            logger.info('The apk is pushed to device/emulator: %s', push_apk)
        else:
            logger.error('Error with pushing!: %s', push_apk)
            raise SystemExit(1)

        # install_package = f'adb install {path_to_apk}'
        apk = os.path.basename(path_to_apk)
        if magisk:
            install_package = (f'adb shell su -c "pm install '
                               f'/data/local/tmp/{apk}"')
        else:
            install_package = (f'adb shell "su 0 pm install '
                               f'/data/local/tmp/{apk}"')

        logger.info('Installing the APK: %s', install_package)
        installation = os.popen(install_package).read()
        logger.debug(installation)
        if 'Success' in installation:
            logger.info('The apk is installed: %s', path_to_apk)
        else:
            logger.error('APK installation error!: %s', path_to_apk)
            raise SystemExit(1)
    else:
        logger.info('The package %s is already installed.', package)

    logger.debug('Exiting the function: "install_apk"')


def start_application(package):
    """Start application on the device or emulator.

    Args:
      package: Package name of apk.

    Returns:
      start_ts: Application launch timestamp.
      pid: Pid of application.

    Raises:
      SystemExit: If runtime error.
    """

    logger.debug('Entering the function: "start_app"')

    start_app_w = (f'adb shell monkey -p {package} -c '
                   'android.intent.category.LAUNCHER 1')
    logger.info('Starting the package: %s', start_app_w)

    if logger.root.level == logging.DEBUG:
        stdout_monkey = None
    else:
        stdout_monkey = subprocess.PIPE

    # proc = subprocess.Popen(start_app_w, shell=True)
    with subprocess.Popen(start_app_w, shell=True,
                          stdout=stdout_monkey,
                          stderr=subprocess.PIPE) as proc:

        # retcode = proc.returncode
        pid = str(proc.pid)
        proc.wait()
    # if bool(retcode):)

    get_running_status = f'adb shell ps | grep {package}'
    logger.info('Getting the application status: %s', package)
    app_status = os.popen(get_running_status).read()
    logger.debug(app_status)
    if len(app_status):
        logger.info('The app is running: %s', package)
    else:
        logger.error('Runtime error!: %s', package)
        stop_mitm()
        raise SystemExit(1)

    now = datetime.now()
    start_ts = datetime.timestamp(now)

    logger.debug('Exiting the function: "start_app"')

    return{'start_timestamp': start_ts, 'pid': pid}


def activity(start_timestamp, activity_time):
    """Emulation of working with the application.

    Args:
      start_timestamp: Application launch timestamp.

    Returns:
      Nothing.

    Raises:
      Nothing.
    """

    logger.debug('Entering the function: "activity"')

    logger.info('Start of activities: %s sec.', activity_time)

    now = datetime.now()
    now_timestamp = datetime.timestamp(now)
    passed_time = now_timestamp - start_timestamp
    while passed_time <= activity_time:
        time.sleep(2)
        now = datetime.now()
        now_timestamp = datetime.timestamp(now)
        passed_time = now_timestamp - start_timestamp

    logger.debug('Exiting the function: "activity"')


def stop_application(package, pid):
    """Stop application on the device or emulator.

    Args:
      package: Package name of apk.
      pid: Pid of application.

    Returns:
      Nothing.

    Raises:
      SystemExit: If error stopping the application.
    """

    logger.debug('Entering the function: "stop_app"')

    stop_app = f'adb shell am force-stop {package}'
    logger.info('Stopping the app: %s', package)
    ret_stop = os.popen(stop_app).read()
    logger.debug(ret_stop)

    check_app = f'adb shell ps -p {pid} | grep {pid}'
    app_status = os.popen(check_app).read()
    logger.debug(app_status)
    if not app_status:
        logger.info('The application is stopped: %s', package)
    else:
        logger.error('Error stopping the application!: %s', package)
        stop_mitm()
        raise SystemExit(1)

    logger.debug('Exiting the function: "stop_app"')


def remove_apk(package):
    """Removing the apk from the device or emulator.

    Args:
      package: Package name of apk.

    Returns:
      Nothing.

    Raises:
      SystemExit: If package uninstallation error.
    """

    logger.debug('Entering the function: "remove_apk"')

    uninstall_package = f'adb shell pm uninstall {package}'
    logger.info('Uninstalling the package: %s', uninstall_package)
    result = os.popen(uninstall_package).read()
    logger.debug(result)
    if 'Success' in result:
        logger.info('The apk is uninstalled: %s', package)
    else:
        logger.error('Package uninstallation error!: %s', package)
        raise SystemExit(1)

    logger.debug('Exiting the function: "remove_apk"')


def make_report(output, report_data):
    """Creates a report based on the results of the analysis.

    Args:
      output: Absolute path of report placement.
      report_data: A set of analysis data.

    Returns:
      Nothing.

    Raises:
      Nothing.
    """

    logger.debug('Entering the function: "make_report"')

    logger.info('Preparing the report...')

    with open(output, 'w') as outfile:
        json.dump(report_data, outfile, indent=4, ensure_ascii=False)

    logger.info('The report has been prepared: %s', output)

    logger.debug('Exiting the function: "make_report"')


def main(path_to_apk, device_ip, su_pass, output, activity_time,
         allow_permissions, tempdir):

    check_command_line(path_to_apk, output)
    start_jadx(path_to_apk, tempdir)
    device_data = check_device()
    badging = get_badging(path_to_apk)
    install_apk(badging['package'], path_to_apk, device_data['magisk'])
    report_data = perform_static_analysis(badging, tempdir)
    report_data = perform_dynamic_analysis(report_data, badging['package'],
                                           activity_time, device_ip,
                                           su_pass, tempdir,
                                           device_data['magisk'])
    remove_apk(badging['package'])
    make_report(output, report_data)


if __name__ == '__main__':

    with tempfile.TemporaryDirectory() as app_tempdir:
        if __debug__:
            app_tempdir = './research'
        logger.info('The temp directory is %s', app_tempdir)
        default_output = f'{app_tempdir}/exynex_output.json'

        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)

        parser.add_argument('analyze', help='Command to analyze.')
        parser.add_argument('PATH_TO_APK', help='Path to APK file.')
        parser.add_argument('device_ip', help='IP address of the device or '
                            'emulator.')
        parser.add_argument('su_pass', help='Superuser password.')
        parser.add_argument('--output', type=str, default=default_output,
                            help='Path to report.')
        parser.add_argument('--activity_time', type=int, default=5,
                            help='Time to activity.')
        parser.add_argument('--allow_permissions',
                            help='Allow to any permissions requests.',
                            action='store_true')
        parser.add_argument('--verbose',
                            help='Produces debugging output.',
                            action='store_true')

        args = parser.parse_args()

        if args.verbose:
            logger.setLevel(logging.DEBUG)

        main(args.PATH_TO_APK, args.device_ip, args.su_pass, args.output,
             args.activity_time, args.allow_permissions, app_tempdir)
