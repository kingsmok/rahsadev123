from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from payments.gateways import post_json


@override_settings(ZARINPAL_ALLOWED_HOSTS=('api.zarinpal.com', 'sandbox.zarinpal.com'))
class PaymentGatewayHostValidationTests(SimpleTestCase):
    def test_rejects_non_https_and_unapproved_hosts_before_network_access(self):
        with patch('payments.gateways.urlopen') as urlopen:
            with self.assertRaisesMessage(ValueError, 'مجاز نیست'):
                post_json('http://api.zarinpal.com/pg/v4/payment/request.json', {})
            with self.assertRaisesMessage(ValueError, 'مجاز نیست'):
                post_json('https://example.test/collect', {})
            urlopen.assert_not_called()

    def test_allows_configured_https_gateway_host(self):
        response = MagicMock()
        response.read.return_value = b'{"data": {"code": 100}}'
        with patch('payments.gateways.urlopen') as urlopen:
            urlopen.return_value.__enter__.return_value = response
            data = post_json('https://api.zarinpal.com/pg/v4/payment/request.json', {'amount': 1})

        self.assertEqual(data['data']['code'], 100)
        self.assertEqual(urlopen.call_args.kwargs['timeout'], 15)
