"""Testes do envio de e-mail: Brevo (HTTPS, usado na nuvem) e Gmail (SMTP, usado no computador).

Nenhum e-mail de verdade é enviado: a chamada à internet é substituída por uma falsa.
"""
import io
import json
import unittest
import urllib.error
from unittest import mock

import servidor


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b'{"messageId": "teste"}'


class EmailTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        for name, value in {"BREVO_API_KEY": "chave-de-teste", "EMAIL_FROM": "hemoflow@exemplo.com",
                            "SUPPORT_EMAIL": "suporte@exemplo.com", "EMAIL_USER": "", "EMAIL_PASSWORD": ""}.items():
            patcher = mock.patch.object(servidor, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_urlopen(self, request, timeout=None):
        self.calls.append(request)
        return FakeResponse()

    def sent_payload(self):
        (request,) = self.calls
        return request, json.loads(request.data)

    def test_recuperacao_de_senha_vai_pelo_brevo(self):
        with mock.patch.object(servidor.urllib.request, "urlopen", self.fake_urlopen):
            servidor.send_recovery_email("ana@exemplo.com", "https://h.exemplo.com/?reset_token=abc", "Ana Souza")
        request, payload = self.sent_payload()
        self.assertEqual(request.full_url, servidor.BREVO_URL)
        self.assertEqual(request.get_header("Api-key"), "chave-de-teste")
        self.assertEqual(payload["sender"], {"name": "HemoFlow", "email": "hemoflow@exemplo.com"})
        self.assertEqual(payload["to"], [{"email": "ana@exemplo.com"}])
        self.assertIn("Criar nova senha", payload["htmlContent"])
        self.assertIn("reset_token=abc", payload["textContent"])

    def test_suporte_vai_pelo_brevo_com_responder_para_o_usuario(self):
        with mock.patch.object(servidor.urllib.request, "urlopen", self.fake_urlopen):
            servidor.send_support_email("SUP-1", "Dúvida", "Assunto", "Texto da mensagem", "Ana", "ana@exemplo.com")
        _, payload = self.sent_payload()
        self.assertEqual(payload["to"], [{"email": "suporte@exemplo.com"}])
        self.assertEqual(payload["replyTo"], {"email": "ana@exemplo.com"})
        self.assertIn("SUP-1", payload["subject"])
        self.assertIn("Texto da mensagem", payload["textContent"])

    def test_brevo_recusou_vira_oserror(self):
        def refused(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"message":"Key not found"}'))
        with mock.patch.object(servidor.urllib.request, "urlopen", refused):
            with self.assertRaises(OSError) as ctx:
                servidor.send_support_email("SUP-1", "Dúvida", "Assunto", "Texto", "Ana", "ana@exemplo.com")
        self.assertIn("401", str(ctx.exception))

    def test_sem_chave_do_brevo_usa_o_gmail(self):
        sent = []

        class FakeSMTP:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def send_message(self, message):
                sent.append(message)

        with mock.patch.object(servidor, "BREVO_API_KEY", ""), \
                mock.patch.object(servidor, "smtp_connection", lambda: FakeSMTP()), \
                mock.patch.object(servidor.urllib.request, "urlopen", self.fake_urlopen):
            servidor.send_support_email("SUP-1", "Dúvida", "Assunto", "Texto", "Ana", "ana@exemplo.com")
        self.assertEqual(len(sent), 1)
        self.assertEqual(self.calls, [])

    def test_email_configurado(self):
        self.assertTrue(servidor.email_configured())                       # Brevo
        with mock.patch.object(servidor, "BREVO_API_KEY", ""):
            self.assertFalse(servidor.email_configured())                  # nada
            with mock.patch.object(servidor, "EMAIL_USER", "x@gmail.com"), \
                    mock.patch.object(servidor, "EMAIL_PASSWORD", "senhadeapp"):
                self.assertTrue(servidor.email_configured())               # Gmail


if __name__ == "__main__":
    unittest.main()
