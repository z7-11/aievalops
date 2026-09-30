from locust import HttpUser, between, task


class CustomerServiceUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def ask_refund_question(self) -> None:
        with self.client.post(
            "/api/chat",
            json={"question": "商品签收后多久可以退款？"},
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"unexpected status: {response.status_code}"
                )
                return

            if "7天" not in response.json()["answer"]:
                response.failure("answer does not contain 7天")

    @task(2)
    def health_check(self) -> None:
        self.client.get("/health")