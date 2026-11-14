"""Pruebas automáticas. Ejecutar con:  python -m unittest discover -s tests -v"""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app = create_app(test_config={"TESTING": True,
                                      "DATABASE": os.path.join(self.tmp.name, "t.db")})
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def token(self, url="/login"):
        html = self.client.get(url).get_data(as_text=True)
        return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)

    def login(self, user="admin", pwd="123"):
        return self.client.post(
            "/login", data={"username": user, "password": pwd, "_csrf": self.token()},
            follow_redirects=True)

    def test_login_incorrecto(self):
        self.assertIn("incorrectos", self.login(pwd="mala").get_data(as_text=True))

    def test_ruta_protegida(self):
        r = self.client.get("/gastos")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_post_sin_csrf_rechazado(self):
        r = self.client.post("/login", data={"username": "admin", "password": "123"})
        self.assertEqual(r.status_code, 400)

    def test_flujo_completo(self):
        self.assertIn("Registro de gastos", self.login().get_data(as_text=True))
        t = self.token("/gastos")
        r = self.client.post("/gastos/nuevo", data={
            "fecha": "2026-11-01", "descripcion": "Almuerzo", "monto": "15.50", "_csrf": t},
            follow_redirects=True).get_data(as_text=True)
        self.assertIn("Almuerzo", r)
        self.assertIn("S/ 15.50", r)

        r = self.client.post("/gastos/1/editar", data={
            "fecha": "2026-11-01", "descripcion": "Cena", "monto": "20", "_csrf": t},
            follow_redirects=True).get_data(as_text=True)
        self.assertIn("Cena", r)

        self.assertIn("S/ 20.00", self.client.get("/reporte").get_data(as_text=True))
        csv_resp = self.client.get("/reporte/exportar.csv")
        self.assertEqual(csv_resp.mimetype, "text/csv")
        self.assertIn("Cena", csv_resp.get_data(as_text=True))

        r = self.client.post("/gastos/1/eliminar", data={"_csrf": t},
                             follow_redirects=True).get_data(as_text=True)
        self.assertIn("No hay gastos", r)

    def test_validacion(self):
        self.login()
        t = self.token("/gastos")
        r = self.client.post("/gastos/nuevo", data={
            "fecha": "xx", "descripcion": "", "monto": "-3", "_csrf": t},
            follow_redirects=True).get_data(as_text=True)
        self.assertIn("fecha no es válida", r)
        self.assertIn("obligatoria", r)
        self.assertIn("mayor que cero", r)

    def test_filtro_por_fechas(self):
        self.login()
        t = self.token("/gastos")
        for f, d, m in [("2026-09-10", "Septiembre", "10"), ("2026-11-05", "Noviembre", "30")]:
            self.client.post("/gastos/nuevo", data={"fecha": f, "descripcion": d, "monto": m, "_csrf": t})
        r = self.client.get("/gastos?desde=2026-11-01").get_data(as_text=True)
        self.assertIn("Noviembre", r)
        self.assertNotIn("Septiembre", r)


if __name__ == "__main__":
    unittest.main()
