import time


class LoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time

        method = request.method
        path = request.get_full_path()
        status_code = response.status_code

        print(
            f"{method} {path} {status_code} - {duration:.4f} seconds"
        )

        return response