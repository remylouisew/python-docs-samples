# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and

import os
import time
from typing import Iterator, Optional, Tuple, Union
import uuid

from google.api_core import exceptions, retry
from google.cloud import secretmanager, secretmanager_v1
import pytest

from regional_samples import create_regional_secret
from regional_samples import delete_regional_secret
from regional_samples import get_regional_secret
from regional_samples import regional_quickstart
from regional_samples import update_regional_secret


@pytest.fixture()
def location_id() -> str:
    return "us-central1"


@pytest.fixture()
def regional_client(location_id: str) -> secretmanager_v1.SecretManagerServiceClient:
    api_endpoint = f"secretmanager.{location_id}.rep.googleapis.com"
    return secretmanager_v1.SecretManagerServiceClient(
        client_options={"api_endpoint": api_endpoint}
    )


@pytest.fixture()
def project_id() -> str:
    return os.environ["GOOGLE_CLOUD_PROJECT"]


@pytest.fixture()
def iam_user() -> str:
    return "serviceAccount:" + os.environ["GCLOUD_SECRETS_SERVICE_ACCOUNT"]


@pytest.fixture()
def ttl() -> Optional[str]:
    return "300s"

@retry.Retry()
def retry_client_create_regional_secret(
    regional_client: secretmanager_v1.SecretManagerServiceClient,
    request: Optional[Union[secretmanager_v1.CreateSecretRequest, dict]],
) -> secretmanager_v1.Secret:
    # Retry to avoid 503 error & flaky issues
    return regional_client.create_secret(request=request)

@retry.Retry()
def retry_client_delete_regional_secret(
    regional_client: secretmanager_v1.SecretManagerServiceClient,
    request: Optional[Union[secretmanager_v1.DeleteSecretRequest, dict]],
) -> None:
    # Retry to avoid 503 error & flaky issues
    return regional_client.delete_secret(request=request)

@retry.Retry()
def retry_client_access_regional_secret_version(
    regional_client: secretmanager_v1.SecretManagerServiceClient,
    request: Optional[Union[secretmanager_v1.AccessSecretVersionRequest, dict]],
) -> secretmanager_v1.AccessSecretVersionResponse:
    # Retry to avoid 503 error & flaky issues
    return regional_client.access_secret_version(request=request)

@pytest.fixture()
def secret_id(
    regional_client: secretmanager.SecretManagerServiceClient,
    project_id: str,
    location_id: str,
) -> Iterator[str]:
    secret_id = f"python-secret-{uuid.uuid4()}"

    yield secret_id
    secret_path = f"projects/{project_id}/locations/{location_id}/secrets/{secret_id}"
    print(f"deleting secret {secret_id}")
    try:
        time.sleep(5)
        retry_client_delete_regional_secret(
            regional_client, request={"name": secret_path}
        )
    except exceptions.NotFound:
        # Secret was already deleted, probably in the test
        print(f"Secret {secret_id} was not found.")


@pytest.fixture()
def regional_secret(
    regional_client: secretmanager_v1.SecretManagerServiceClient,
    project_id: str,
    location_id: str,
    secret_id: str,
    ttl: Optional[str],
) -> Iterator[Tuple[str, str, str, str]]:
    print(f"creating secret {secret_id}")

    parent = f"projects/{project_id}/locations/{location_id}"
    time.sleep(5)
    regional_secret = retry_client_create_regional_secret(
        regional_client,
        request={
            "parent": parent,
            "secret_id": secret_id,
            "secret": {"ttl": ttl},
        },
    )

    yield project_id, location_id, secret_id, regional_secret.etag


def test_regional_quickstart(project_id: str, location_id: str, secret_id: str) -> None:
    regional_quickstart.regional_quickstart(project_id, location_id, secret_id)


def test_create_regional_secret(
    regional_client: secretmanager_v1.SecretManagerServiceClient,
    project_id: str,
    location_id: str,
    secret_id: str,
    ttl: Optional[str],
) -> None:
    secret = create_regional_secret.create_regional_secret(project_id, location_id, secret_id, ttl)
    assert secret_id in secret.name


def test_delete_regional_secret(
    regional_client: secretmanager_v1.SecretManagerServiceClient,
    regional_secret: Tuple[str, str, str, str],
) -> None:
    project_id, location_id, secret_id, _ = regional_secret
    delete_regional_secret.delete_regional_secret(project_id, location_id, secret_id)
    with pytest.raises(exceptions.NotFound):
        print(f"{regional_client}")
        name = f"projects/{project_id}/locations/{location_id}/secrets/{secret_id}/versions/latest"
        retry_client_access_regional_secret_version(
            regional_client, request={"name": name}
        )


def test_get_regional_secret(
    regional_client: secretmanager_v1.SecretManagerServiceClient,
    regional_secret: Tuple[str, str, str, str],
) -> None:
    project_id, location_id, secret_id, _ = regional_secret
    snippet_regional_secret = get_regional_secret.get_regional_secret(project_id, location_id, secret_id)
    assert secret_id in snippet_regional_secret.name


def test_update_regional_secret(regional_secret: Tuple[str, str, str, str]) -> None:
    project_id, location_id, secret_id, _ = regional_secret
    updated_regional_secret = update_regional_secret.update_regional_secret(project_id, location_id, secret_id)
    assert updated_regional_secret.labels["secretmanager"] == "rocks"
