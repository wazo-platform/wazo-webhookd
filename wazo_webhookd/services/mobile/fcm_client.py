# Copyright 2024-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright 2019 Emmanuel Adegbite
# SPDX-License-Identifier: MIT

import json
import logging
import os
import threading
import time
from typing import Protocol

import google.auth.transport.requests
import requests
from google.oauth2 import service_account
from pyfcm import FCMNotification as FCMNotificationLegacyBase
from requests.adapters import HTTPAdapter
from urllib3 import Retry

logger = logging.getLogger(__name__)


class FCMError(Exception):
    """
    FCM Error
    """

    pass


class AuthenticationError(FCMError):
    """
    API key not found or there was an error authenticating the sender
    """

    pass


class FCMNotRegisteredError(FCMError):
    """
    push token is not registered
    https://firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode
    """

    pass


class FCMSenderIDMismatch(FCMError):
    """
    mobile app is registered to another senderid
    https://firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode
    """

    pass


class FCMServerError(FCMError):
    """
    Internal server error or timeout error on Firebase cloud messaging server
    """

    pass


class InvalidDataError(FCMError):
    """
    Invalid input
    """

    pass


class InternalPackageError(FCMError):
    """
    JSON parsing error, please create a new github issue describing what you're doing
    """

    pass


class RetryAfterException(Exception):
    """
    Retry-After must be handled by external logic.
    """

    def __init__(self, delay):
        self.delay = delay


class BaseAPI:
    """
    Base class for the API wrapper for FCM

    Attributes:
        service_account_info (str | dict): path to the service account file or dict content
        proxy_dict (dict): use proxy (keys: `http`, `https`)
        json_encoder
        adapter: requests.adapters.HTTPAdapter()
    """

    CONTENT_TYPE = "application/json"
    FCM_END_POINT: str = (
        "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    )
    FCM_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

    #: Indicates that the push message should be sent with low priority. Low
    #: priority optimizes the client app's battery consumption, and should be used
    #: unless immediate delivery is required. For messages with low priority, the
    #: app may receive the message with unspecified delay.
    FCM_LOW_PRIORITY = "normal"

    #: Indicates that the push message should be sent with a high priority. When a
    #: message is sent with high priority, it is sent immediately, and the app can
    #: wake a sleeping device and open a network connection to your server.
    FCM_HIGH_PRIORITY = "high"

    def __init__(
        self,
        service_account_info=None,
        proxy_dict=None,
        json_encoder=None,
        adapter=None,
    ):
        if service_account_info:
            self._FCM_ACCOUNT_INFO = service_account_info
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None):
            self._FCM_ACCOUNT_INFO = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None)
        else:
            raise AuthenticationError(
                "Please provide the service account info containing credentials"
            )

        self.FCM_REQ_PROXIES = None
        self.custom_adapter = adapter
        self.thread_local = threading.local()

        if (
            proxy_dict
            and isinstance(proxy_dict, dict)
            and (("http" in proxy_dict) or ("https" in proxy_dict))
        ):
            self.FCM_REQ_PROXIES = proxy_dict
            self.requests_session.proxies.update(proxy_dict)

        self.send_request_responses = []
        self.json_encoder = json_encoder

    @property
    def requests_session(self):
        if getattr(self.thread_local, "requests_session", None) is None:
            retries = Retry(
                backoff_factor=1,
                status_forcelist=[502, 503],
                allowed_methods=(Retry.DEFAULT_ALLOWED_METHODS | frozenset(["POST"])),
            )
            adapter = self.custom_adapter or HTTPAdapter(max_retries=retries)
            self.thread_local.requests_session = requests.Session()
            self.thread_local.requests_session.mount("http://", adapter)
            self.thread_local.requests_session.mount("https://", adapter)
            self.thread_local.requests_session.headers.update(self.request_headers())

        return self.thread_local.requests_session

    def _get_access_token(self):
        """Retrieve a valid access token that can be used to authorize requests.

        :return: Access token.
        """
        credentials = service_account.Credentials.from_service_account_info(
            self._FCM_ACCOUNT_INFO, scopes=self.FCM_SCOPES
        )
        self._credentials = credentials
        self._project_id = credentials.project_id
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        self.FCM_END_POINT = self.FCM_END_POINT.format(project_id=self._project_id)
        logger.debug('FCM endpoint: %s', self.FCM_END_POINT)

        return credentials.token

    def request_headers(self):
        """
        Generates request headers including Content-Type and Authorization

        Returns:
            dict: request headers
        """
        return {
            "Content-Type": self.CONTENT_TYPE,
            "Authorization": "Bearer " + self._get_access_token(),
        }

    def json_dumps(self, data):
        """
        Standardized json.dumps function with separators and sorted keys set

        Args:
            data (dict or list): data to be dumped

        Returns:
            string: json
        """
        return json.dumps(
            data,
            separators=(",", ":"),
            sort_keys=True,
            cls=self.json_encoder,
            ensure_ascii=False,
        ).encode("utf8")

    def parse_payload(
        self,
        registration_token=None,
        message_body=None,
        message_title=None,
        message_icon=None,
        sound=None,
        collapse_key=None,
        time_to_live=None,
        restricted_package_name=None,
        low_priority=False,
        dry_run=False,
        data_message=None,
        click_action=None,
        badge=None,
        color=None,
        tag=None,
        body_loc_key=None,
        body_loc_args=None,
        title_loc_key=None,
        title_loc_args=None,
        remove_notification=False,
        android_channel_id=None,
        extra_notification_kwargs={},
        **extra_kwargs,
    ):
        """
        Parses parameters of FCMNotification's methods to FCM nested json

        Args:
            registration_token (str, optional): FCM device registration token
            message_body (str, optional): Message string to display in the notification tray
            message_title (str, optional): Message title to display in the notification tray
            message_icon (str, optional): Icon that apperas next to the notification
            sound (str, optional): The sound file name to play. Specify "Default" for device
                                   default sound.
            collapse_key (str, optional): Identifier for a group of messages
                that can be collapsed so that only the last message gets sent
                when delivery can be resumed. Defaults to `None`.
            time_to_live (int, optional): How long (in seconds) the message
                should be kept in FCM storage if the device is offline. The
                maximum time to live supported is 4 weeks. Defaults to `None`
                which uses the FCM default of 4 weeks.
            restricted_package_name (str, optional): Name of package
            low_priority (bool, optional): Whether to send notification with
                the low priority flag. Defaults to `False`.
            dry_run (bool, optional): If `True` no message will be sent but request will be tested.
            data_message (dict, optional): Custom key-value pairs
            click_action (str, optional): Action associated with a user click on the notification
            badge (str, optional): Badge of notification
            color (str, optional): Color of the icon
            tag (str, optional): Group notification by tag
            body_loc_key (str, optional): Indicates the key to the body string for localization
            body_loc_args (list, optional): Indicates the string value to replace format
                specifiers in body string for localization
            title_loc_key (str, optional): Indicates the key to the title string for localization
            title_loc_args (list, optional): Indicates the string value to replace format
                specifiers in title string for localization
            remove_notification (bool, optional): Only send a data message
            android_channel_id (str, optional): Starting in Android 8.0 (API level 26),
                all notifications must be assigned to a channel. For each channel, you can set the
                visual and auditory behavior that is applied to all notifications in that channel.
                Then, users can change these settings and decide which notification channels from
                your app should be intrusive or visible at all.
            extra_notification_kwargs (dict, optional): More notification keyword arguments
            **extra_kwargs (dict, optional): More keyword arguments

        Returns:
            string: json

        Raises:
            InvalidDataError: parameters do have the wrong type or format
        """
        fcm_payload = dict()
        android_config_payload = dict()
        android_notification_payload = dict()

        if registration_token:
            fcm_payload["token"] = registration_token

        if low_priority:
            android_config_payload["priority"] = self.FCM_LOW_PRIORITY
        else:
            android_config_payload["priority"] = self.FCM_HIGH_PRIORITY

        if collapse_key:
            android_config_payload["collapse_key"] = collapse_key
        if time_to_live is not None:
            if isinstance(time_to_live, int):
                android_config_payload["ttl"] = f"{time_to_live}s"
            else:
                raise InvalidDataError("Provided time_to_live is not an integer")
        if restricted_package_name:
            android_config_payload["restricted_package_name"] = restricted_package_name
        if dry_run:
            fcm_payload["dry_run"] = dry_run

        if data_message:
            if isinstance(data_message, dict):
                fcm_payload["data"] = data_message
            else:
                raise InvalidDataError("Provided data_message is in the wrong format")

        if message_icon:
            android_notification_payload["icon"] = message_icon
        # If body is present, use it
        if message_body:
            android_notification_payload["body"] = message_body
        # Else use body_loc_key and body_loc_args for body
        else:
            if body_loc_key:
                android_notification_payload["body_loc_key"] = body_loc_key
            if body_loc_args:
                if isinstance(body_loc_args, list):
                    android_notification_payload["body_loc_args"] = body_loc_args
                else:
                    raise InvalidDataError("body_loc_args should be an array")
        # If title is present, use it
        if message_title:
            android_notification_payload["title"] = message_title
        # Else use title_loc_key and title_loc_args for title
        else:
            if title_loc_key:
                android_notification_payload["title_loc_key"] = title_loc_key
            if title_loc_args:
                if isinstance(title_loc_args, list):
                    android_notification_payload["title_loc_args"] = title_loc_args
                else:
                    raise InvalidDataError("title_loc_args should be an array")

        if android_channel_id:
            android_notification_payload["channel_id"] = android_channel_id

        if click_action:
            android_notification_payload["click_action"] = click_action
        if isinstance(badge, int) and badge >= 0:
            android_notification_payload["notification_count"] = badge
        if color:
            android_notification_payload["color"] = color
        if tag:
            android_notification_payload["tag"] = tag
        # only add the 'sound' key if sound is not None
        # otherwise a default sound will play -- even with empty string args.
        if sound:
            android_notification_payload["sound"] = sound

        if extra_kwargs:
            fcm_payload.update(extra_kwargs)

        if extra_notification_kwargs:
            android_notification_payload.update(extra_notification_kwargs)

        if android_config_payload:
            fcm_payload["android"] = android_config_payload
            if android_notification_payload and not remove_notification:
                fcm_payload["android"]["notification"] = android_notification_payload

        message = {"message": fcm_payload}
        return self.json_dumps(message)

    def do_request(self, payload, timeout):
        logger.debug('FCM request payload: %s', payload)
        response = self.requests_session.post(
            self.FCM_END_POINT, data=payload, timeout=timeout
        )
        if (
            "Retry-After" in response.headers
            and int(response.headers["Retry-After"]) > 0
        ):
            sleep_time = int(response.headers["Retry-After"])
            time.sleep(sleep_time)
            return self.do_request(payload, timeout)
        return response

    def send_request(self, payloads: list[str], timeout: int) -> None:
        self.send_request_responses = []
        for payload in payloads:
            response = self.do_request(payload, timeout)
            self.send_request_responses.append(response)

    def parse_responses(self):
        """
        Parses the json response sent back by the server and tries to get out the important return
        variables

        Returns:
            dict: multicast_ids (list), success (int), failure (int), canonical_ids (int),
                results (list) and optional topic_message_id (str but None by default)

        Raises:
            FCMServerError: FCM is temporary not available
            AuthenticationError: error authenticating the sender account
            InvalidDataError: data passed to FCM was incorrecly structured
        """
        response_dict = {
            "multicast_ids": [],
            "success": 0,
            "failure": 0,
            "canonical_ids": 0,
            "results": [],
            "topic_message_id": None,
        }

        for response in self.send_request_responses:
            if response.status_code == 200:
                if (
                    "content-length" in response.headers
                    and int(response.headers["content-length"]) <= 0
                ):
                    raise FCMServerError(
                        "FCM server connection error, the response is empty"
                    )
                else:
                    parsed_response = response.json()
                    logger.debug('Raw FCM response: %s', parsed_response)

                    if message_id := parsed_response.get("name", None):
                        response_dict["success"] = 1
                        response_dict["topic_message_id"] = message_id
                        response_dict["results"] = [parsed_response]
                    else:
                        response_dict["failure"] = 1

            elif response.status_code == 401:
                raise AuthenticationError(
                    "There was an error authenticating the sender account"
                )
            elif response.status_code == 400:
                raise InvalidDataError(response.text)
            elif response.status_code == 403:
                raise FCMSenderIDMismatch(response.json()['error'])
            elif response.status_code == 404:
                raise FCMNotRegisteredError("Token not registered")
            else:
                try:
                    error = response.json()['error']
                except (json.JSONDecodeError, KeyError):
                    error = response.text
                raise FCMServerError(error)
        return response_dict


class FCMNotification(BaseAPI):
    def notify_single_device(
        self,
        registration_token,
        message_body=None,
        message_title=None,
        message_icon=None,
        sound=None,
        collapse_key=None,
        time_to_live=None,
        restricted_package_name=None,
        low_priority=False,
        dry_run=False,
        data_message=None,
        click_action=None,
        badge=None,
        color=None,
        tag=None,
        body_loc_key=None,
        body_loc_args=None,
        title_loc_key=None,
        title_loc_args=None,
        android_channel_id=None,
        timeout=120,
        extra_notification_kwargs=None,
        extra_kwargs={},
    ):
        """
        Send push notification to a single device

        Args:
            registration_token (list, optional): FCM device registration token
            message_body (str, optional): Message string to display in the notification tray
            message_title (str, optional): Message title to display in the notification tray
            message_icon (str, optional): Icon that apperas next to the notification
            sound (str, optional): The sound file name to play. Specify "Default" for device
                                   default sound.
            collapse_key (str, optional): Identifier for a group of messages
                that can be collapsed so that only the last message gets sent
                when delivery can be resumed. Defaults to `None`.
            time_to_live (int, optional): How long (in seconds) the message
                should be kept in FCM storage if the device is offline. The
                maximum time to live supported is 4 weeks. Defaults to `None`
                which uses the FCM default of 4 weeks.
            restricted_package_name (str, optional): Name of package
            low_priority (bool, optional): Whether to send notification with
                the low priority flag. Defaults to `False`.
            dry_run (bool, optional): If `True` no message will be sent but request will be tested.
            data_message (dict, optional): Custom key-value pairs
            click_action (str, optional): Action associated with a user click on the notification
            badge (str, optional): Badge of notification
            color (str, optional): Color of the icon
            tag (str, optional): Group notification by tag
            body_loc_key (str, optional): Indicates the key to the body string for localization
            body_loc_args (list, optional): Indicates the string value to replace format
                specifiers in body string for localization
            title_loc_key (str, optional): Indicates the key to the title string for localization
            title_loc_args (list, optional): Indicates the string value to replace format
                specifiers in title string for localization
            android_channel_id (str, optional): Starting in Android 8.0 (API level 26),
                all notifications must be assigned to a channel. For each channel, you can set the
                visual and auditory behavior that is applied to all notifications in that channel.
                Then, users can change these settings and decide which notification channels from
                your app should be intrusive or visible at all.
            timeout (int, optional): set time limit for the request
            extra_notification_kwargs (dict, optional): More notification keyword arguments
            extra_kwargs (dict, optional): More keyword arguments

        Returns:
            dict: Response from FCM server (Message instance, which only has the `name` field)

        Raises:
            AuthenticationError: If :attr:`service_account_file` is not set or provided
                or there is an error authenticating the sender.
            FCMServerError: Internal server error or timeout error on Firebase cloud messaging
                            server
            InvalidDataError: Invalid data provided
            InternalPackageError: Mostly from changes in the response of FCM,
                contact the project owner to resolve the issue
        """

        payload = self.parse_payload(
            registration_token=registration_token,
            message_body=message_body,
            message_title=message_title,
            message_icon=message_icon,
            sound=sound,
            collapse_key=collapse_key,
            time_to_live=time_to_live,
            restricted_package_name=restricted_package_name,
            low_priority=low_priority,
            dry_run=dry_run,
            data_message=data_message,
            click_action=click_action,
            badge=badge,
            color=color,
            tag=tag,
            body_loc_key=body_loc_key,
            body_loc_args=body_loc_args,
            title_loc_key=title_loc_key,
            title_loc_args=title_loc_args,
            android_channel_id=android_channel_id,
            extra_notification_kwargs=extra_notification_kwargs,
            **extra_kwargs,
        )

        self.send_request([payload], timeout)
        return self.parse_responses()

    def single_device_data_message(
        self,
        registration_token=None,
        collapse_key=None,
        time_to_live=None,
        restricted_package_name=None,
        low_priority=False,
        dry_run=False,
        data_message=None,
        android_channel_id=None,
        timeout=120,
        extra_notification_kwargs=None,
        extra_kwargs={},
    ):
        """
        Send push message to a single device

        Args:
            registration_token (str, optional): FCM device registration token
            collapse_key (str, optional): Identifier for a group of messages
                that can be collapsed so that only the last message gets sent
                when delivery can be resumed. Defaults to `None`.
            time_to_live (int, optional): How long (in seconds) the message
                should be kept in FCM storage if the device is offline. The
                maximum time to live supported is 4 weeks. Defaults to `None`
                which uses the FCM default of 4 weeks.
            restricted_package_name (str, optional): Name of package
            low_priority (bool, optional): Whether to send notification with
                the low priority flag. Defaults to `False`.
            dry_run (bool, optional): If `True` no message will be sent but request will be tested.
            data_message (dict, optional): Custom key-value pairs
            android_channel_id (str, optional): Starting in Android 8.0 (API level 26),
                all notifications must be assigned to a channel. For each channel, you can set the
                visual and auditory behavior that is applied to all notifications in that channel.
                Then, users can change these settings and decide which notification channels from
                your app should be intrusive or visible at all.
            timeout (int, optional): set time limit for the request
            extra_notification_kwargs (dict, optional): More notification keyword arguments
            extra_kwargs (dict, optional): More keyword arguments

        Returns:
            dict: Response from FCM server (Message instance, which only has the `name` field)

        Raises:
            AuthenticationError: If :attr:`api_key` is not set or provided
                or there is an error authenticating the sender.
            FCMServerError: Internal server error or timeout error on Firebase cloud messaging
                            server
            InvalidDataError: Invalid data provided
            InternalPackageError: Mostly from changes in the response of FCM,
                contact the project owner to resolve the issue
        """
        if registration_token is None:
            raise InvalidDataError("Invalid registration ID")
        payload = self.parse_payload(
            registration_token=registration_token,
            collapse_key=collapse_key,
            time_to_live=time_to_live,
            restricted_package_name=restricted_package_name,
            low_priority=low_priority,
            dry_run=dry_run,
            data_message=data_message,
            remove_notification=True,
            android_channel_id=android_channel_id,
            extra_notification_kwargs=extra_notification_kwargs,
            **extra_kwargs,
        )

        self.send_request([payload], timeout)
        return self.parse_responses()


class FCMNotificationLegacy(FCMNotificationLegacyBase):
    def parse_responses(self):
        # rewrite parse_responses to provide more transparent error handling
        # to help debugging
        # otherwise some conditions are misclassified as FCM server availability errors
        # e.g. invalid tokens
        try:
            return super().parse_responses()
        except FCMServerError:
            # inspect the error responses
            error_responses: list[requests.Response] = [
                response
                for response in self.send_request_responses
                if response.status_code not in (200, 401, 400)
            ]
            for response in error_responses:
                logger.error(
                    'FCM error: status=%d, text=%s',
                    response.status_code,
                    response.text,
                )
            raise FCMServerError(
                error_responses[-1].status_code, error_responses[-1].text
            )


# simplified interface for fcm notification clients
# based on the methods we use
class FCMNotificationProtocol(Protocol):
    FCM_END_POINT: str

    def notify_single_device(
        self,
        registration_token,
        message_body=None,
        message_title=None,
        message_icon=None,
        sound=None,
        collapse_key=None,
        time_to_live=None,
        restricted_package_name=None,
        low_priority=False,
        dry_run=False,
        data_message=None,
        click_action=None,
        badge=None,
        color=None,
        tag=None,
        body_loc_key=None,
        body_loc_args=None,
        title_loc_key=None,
        title_loc_args=None,
        android_channel_id=None,
        timeout=120,
        extra_notification_kwargs=None,
        extra_kwargs={},
    ):
        ...

    def single_device_data_message(
        self,
        registration_token,
        collapse_key=None,
        time_to_live=None,
        restricted_package_name=None,
        low_priority=False,
        dry_run=False,
        data_message=None,
        android_channel_id=None,
        timeout=120,
        extra_notification_kwargs=None,
        extra_kwargs={},
    ):
        ...
