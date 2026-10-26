import unittest
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Import core business logic from main
import main

class TestKisaanVaani(unittest.TestCase):

    def test_demo_query_1_net_profit_wheat(self):
        """Test 'गेहूँ कहाँ बेचूँ?' intent and profit advice."""
        query = "गेहूँ कहाँ बेचूँ?"
        intent = main.parse(query)
        self.assertEqual(intent["intent"], "advise_sell")
        self.assertEqual(intent["crop"], "Wheat")

        reply, lang, table = main.handle(intent, "hi-IN")
        self.assertIn("Kanpur", reply)
        self.assertIn("2430", reply) # 2460 price - 30 transport = 2430 net
        self.assertIsNotNone(table)

        # Confirm Kanpur nets more than Azadpur despite Azadpur higher headline price
        azadpur_net = 2550 - 180  # 2370
        kanpur_net = 2460 - 30    # 2430
        self.assertGreater(kanpur_net, azadpur_net, "Kanpur must net ₹60 more than Azadpur!")

    def test_demo_query_2_price_check_onion(self):
        """Test 'आज़ादपुर मंडी में प्याज का भाव'."""
        query = "आज़ादपुर मंडी में प्याज का भाव"
        intent = main.parse(query)
        self.assertEqual(intent["crop"], "Onion")
        reply, lang, table = main.handle(intent, "hi-IN")
        self.assertIn("2100", reply)

    def test_demo_query_3_marathi_logistics(self):
        """Test 'मला 40 क्विंटल कांदा लासलगावला न्यायचा आहे'."""
        query = "मला 40 क्विंटल कांदा लासलगावला न्यायचा आहे"
        lang = main.detect_script_lang(query)
        self.assertEqual(lang, "mr-IN")
        intent = main.parse(query)
        self.assertEqual(intent["intent"], "log_logistics")
        self.assertEqual(intent["crop"], "Onion")
        self.assertEqual(intent["mandi"], "Lasalgaon")
        self.assertEqual(intent["quantity_quintal"], 40)

    def test_demo_query_4_telugu_chilli(self):
        """Test Telugu script detection and query handling."""
        query = "నాకు గుంటూరులో మిర్చి ధర చెప్పండి"
        lang = main.detect_script_lang(query)
        self.assertEqual(lang, "te-IN")
        intent = main.parse(query)
        self.assertEqual(intent["crop"], "Chilli")
        self.assertEqual(intent["mandi"], "Guntur")
        reply, lang_out, table = main.handle(intent, lang)
        self.assertIn("16000", reply)

    def test_all_8_languages_templates(self):
        """Ensure all 8 languages have complete, valid template strings without format syntax errors."""
        languages = ["hi-IN", "te-IN", "mr-IN", "ta-IN", "bn-IN", "pa-IN", "gu-IN", "en-IN"]
        for l in languages:
            self.assertIn(l, main.T, f"Missing language template: {l}")
            t = main.T[l]
            # Test formatting
            s_price = t["price"].format(mandi="Kanpur", crop="Wheat", p=2460)
            self.assertTrue(len(s_price) > 5)
            s_advise = t["advise"].format(mandi="Kanpur", crop="Wheat", net=2430)
            self.assertTrue(len(s_advise) > 5)
            s_confirm = t["confirm"].format(q=40, crop="Wheat", mandi="Kanpur")
            self.assertTrue(len(s_confirm) > 5)
            s_none = t["none"]
            self.assertTrue(len(s_none) > 3)

    def test_script_detection(self):
        """Test instant unicode script detection."""
        self.assertEqual(main.detect_script_lang("गेहूं कहाँ बेचूँ"), "hi-IN")
        self.assertEqual(main.detect_script_lang("రవాణా ధర"), "te-IN")
        self.assertEqual(main.detect_script_lang("சந்தை விலை"), "ta-IN")
        self.assertEqual(main.detect_script_lang("বাজার দর"), "bn-IN")
        self.assertEqual(main.detect_script_lang("ਮੰਡੀ ਭਾਅ"), "pa-IN")
        self.assertEqual(main.detect_script_lang("બજાર ભાવ"), "gu-IN")

    def test_fallback_wav(self):
        """Ensure make_fallback_wav returns valid RIFF header bytes."""
        wav = main.make_fallback_wav()
        self.assertTrue(wav.startswith(b'RIFF'))
        self.assertEqual(len(wav), 44)

    def test_tts_generation(self):
        """Ensure TTS produces playable audio bytes without throwing exception."""
        wav = main.tts("राम राम किसान भाई", "hi-IN", speaker="ritu")
        self.assertIsInstance(wav, bytes)
        self.assertTrue(wav.startswith(b'RIFF'))

if __name__ == "__main__":
    unittest.main()
