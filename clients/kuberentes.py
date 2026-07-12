import asyncio
from kubernetes import client, config as k8s_config, watch
from kubernetes.client.exceptions import ApiException
from utils.logger import get_logger
from utils.custom_errors import InfraNotFoundError


class KubernetesClient:
    def __init__(self, namespace: str = "default") -> None:
        self.logger = get_logger(__name__)
        self.namespace = namespace
        k8s_config.load_incluster_config()
        self.core = client.CoreV1Api()

    def _pod_name(self, project_id: str) -> str:
        return f"sandbox-{project_id}"

    def _service_name(self, project_id: str) -> str:
        return f"sandbox-{project_id}"

    def _labels(self, project_id: str) -> dict:
        return {"app": "sandbox", "project-id": project_id}

    def _create_pod_sync(self, project_id: str, image: str) -> None:
        pod_name = self._pod_name(project_id)
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                labels=self._labels(project_id),
            ),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name="sandbox",
                        image=image,
                        image_pull_policy="IfNotPresent",
                        ports=[client.V1ContainerPort(container_port=9000)],
                        readiness_probe=client.V1Probe(
                            http_get=client.V1HTTPGetAction(path="/sandbox/api/ready", port=9000),
                            period_seconds=1,
                            failure_threshold=3,
                        ),
                        liveness_probe=client.V1Probe(
                            http_get=client.V1HTTPGetAction(path="/sandbox/api/health", port=9000),
                            initial_delay_seconds=5,
                            period_seconds=10,
                        ),
                    )
                ],
                restart_policy="Never",
            ),
        )
        self.core.create_namespaced_pod(namespace=self.namespace, body=pod)
        self.logger.info("Pod created for project '%s'", project_id)

        w = watch.Watch()
        for event in w.stream(
            self.core.list_namespaced_pod,
            namespace=self.namespace,
            field_selector=f"metadata.name={pod_name}",
            timeout_seconds=60,
        ):
            pod_obj = event["object"]
            conditions = pod_obj.status.conditions or []
            if any(c.type == "Ready" and c.status == "True" for c in conditions):
                w.stop()
                self.logger.info("Pod ready for project '%s'", project_id)
                return

        raise RuntimeError(f"Pod '{pod_name}' did not become Ready within timeout")

    def _create_service_sync(self, project_id: str) -> None:
        service = client.V1Service(
            metadata=client.V1ObjectMeta(name=self._service_name(project_id)),
            spec=client.V1ServiceSpec(
                selector=self._labels(project_id),
                ports=[client.V1ServicePort(port=9000, target_port=9000)],
                type="ClusterIP",
            ),
        )
        self.core.create_namespaced_service(namespace=self.namespace, body=service)
        self.logger.info("Service created for project '%s'", project_id)

    def _get_pod_sync(self, project_id: str):
        # raises InfraNotFoundError if infra not found
        pod_name = self._pod_name(project_id)
        try:
            self.core.read_namespaced_pod(name=pod_name, namespace=self.namespace)
        except ApiException as e:
            if e.status == 404:
                raise InfraNotFoundError(f"Sandbox infra not found for project '{project_id}'", status_code=404)
            raise


    def _delete_pod_sync(self, project_id: str) -> None:
        self.core.delete_namespaced_pod(
            name=self._pod_name(project_id),
            namespace=self.namespace,
        )
        self.logger.info("Pod deleted for project '%s'", project_id)

    def _delete_service_sync(self, project_id: str) -> None:
        self.core.delete_namespaced_service(
            name=self._service_name(project_id),
            namespace=self.namespace,
        )
        self.logger.info("Service deleted for project '%s'", project_id)

    async def create_infra(self, project_id: str, image: str) -> None:
        await asyncio.to_thread(self._create_pod_sync, project_id, image)
        await asyncio.to_thread(self._create_service_sync, project_id)

    async def get_infra(self, project_id: str) -> None:
        await asyncio.to_thread(self._get_pod_sync, project_id)

    async def delete_infra(self, project_id: str) -> None:
        await asyncio.to_thread(self._delete_service_sync, project_id)
        await asyncio.to_thread(self._delete_pod_sync, project_id)

    def service_url(self, project_id: str, port: int = 9000) -> str:
        return f"http://{self._service_name(project_id)}.{self.namespace}.svc.cluster.local:{port}"
