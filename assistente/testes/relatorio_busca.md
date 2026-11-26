# Assistente HemoFlow: relatório dos testes

Projeto de José Kaike Gomes dos Santos e João Manoel da Silva Oliveira.

Gerado em 20/11/2026 12:24 · modelo de embeddings `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` · top-k 4 · limiar 0.35


## 1. O que é o HemoFlow?

*Esperado:* Seção 1 (plataforma de captação e fidelização)

*Trechos recuperados:* 1. Sobre o hemoflow: “O que é o HemoFlow?” (1.00); 1. Sobre o hemoflow: “Quem usa o HemoFlow?” (0.82); 12. Conta, privacidade e lgpd: “Como o HemoFlow trata os dados de saúde?” (0.68)


## 2. Tenho 17 anos, posso doar sangue?

*Esperado:* Seção 2: pode com autorização do responsável; triagem decide

*Trechos recuperados:* 2. Quem pode doar (orientação geral): “Quem pode doar sangue?” (0.68); 2. Quem pode doar (orientação geral): “Menores de 18 anos podem doar?” (0.65); 2. Quem pode doar (orientação geral): “Tenho uma dúvida de saúde (remédio, doença, tatuagem, viagem, vacina). Posso doar?” (0.62)


## 3. Quanto tempo uma mulher precisa esperar entre uma doação e outra?

*Esperado:* Seção 3: 90 dias

*Trechos recuperados:* 3. Intervalos e limites entre doações: “Quanto tempo preciso esperar entre uma doação e outra?” (0.88); 3. Intervalos e limites entre doações: “Quantas vezes posso doar por ano?” (0.74); 3. Intervalos e limites entre doações: “Como o app sabe quando posso doar de novo?” (0.64)


## 4. Sou O+, para quem posso doar?

*Esperado:* Seção 4: O+, A+, B+, AB+

*Trechos recuperados:* 10. Grupos de doação e conquistas: “Posso compartilhar a minha doação?” (0.63); 2. Quem pode doar (orientação geral): “Quem pode doar sangue?” (0.61); 6. Convocações e agendamento: “Como agendo uma doação?” (0.59)


## 5. O que significa quando o termômetro está em Atenção?

*Esperado:* Seção 5: estoque baixando

*Trechos recuperados:* 5. Termômetro da doação: “Quem informa o nível do termômetro?” (0.83); 5. Termômetro da doação: “O termômetro mostra o estoque do HEMOPE?” (0.83); 5. Termômetro da doação: “O que significam as cores do termômetro?” (0.75)


## 6. Como a minha doação é confirmada no banco de sangue?

*Esperado:* Seção 7: código de 6 dígitos

*Trechos recuperados:* 7. Registro e confirmação da doação: “Como a minha doação é confirmada?” (0.83); 8. Benefícios e direitos do doador: “Doador de sangue tem isenção de taxa em concurso em Pernambuco?” (0.71); 2. Quem pode doar (orientação geral): “Quem pode doar sangue?” (0.71)


## 7. Doei no HEMOPE, como registro no app?

*Esperado:* Seção 7: Perfil > Histórico, doação declarada

*Trechos recuperados:* 11. Onde doar: “Posso agendar no HEMOPE pelo app?” (0.70); 3. Intervalos e limites entre doações: “Como o app sabe quando posso doar de novo?” (0.62); 13. Uso do aplicativo: “Como instalo o app no celular?” (0.56)


## 8. Como funciona a isenção de taxa de concurso em Pernambuco?

*Esperado:* Seção 8: 3 homens / 2 mulheres em 12 meses; declaração da entidade

*Trechos recuperados:* 8. Benefícios e direitos do doador: “Doador de sangue tem isenção de taxa em concurso em Pernambuco?” (0.69); 8. Benefícios e direitos do doador: “Como comprovo a isenção no concurso?” (0.52); 11. Onde doar: “Em quais cidades de Pernambuco o HEMOPE tem unidades?” (0.52)


## 9. Por que não consigo gerar cupom?

*Esperado:* Seção 9: precisa de doação verificada nos últimos 6 meses

*Trechos recuperados:* 9. Vantagens e cupons: “Como funciona o cupom?” (0.55); 9. Vantagens e cupons: “Quem pode gerar cupons de vantagens?” (0.28); 13. Uso do aplicativo: “Posso aumentar a letra ou usar o modo escuro?” (0.24)


## 10. Quando posso doar de novo?

*Esperado:* Ferramenta quando_posso_doar (doador logado)

*Trechos recuperados:* 3. Intervalos e limites entre doações: “Quantas vezes posso doar por ano?” (0.68); 3. Intervalos e limites entre doações: “Quanto tempo preciso esperar entre uma doação e outra?” (0.67); 10. Grupos de doação e conquistas: “Posso compartilhar a minha doação?” (0.58)


## 11. Como está minha meta de isenção?

*Esperado:* Ferramenta minha_meta_isencao (doador logado)

*Trechos recuperados:* 8. Benefícios e direitos do doador: “Como comprovo a isenção no concurso?” (0.52); 6. Convocações e agendamento: “Posso ter mais de um agendamento?” (0.48); 6. Convocações e agendamento: “O que acontece se eu faltar?” (0.47)


## 12. Como está o estoque de O- no Banco Vida?

*Esperado:* Ferramenta nivel_do_estoque (nível + data, sem quantidade)

*Trechos recuperados:* 5. Termômetro da doação: “O que é o Termômetro da Doação?” (0.43); 1. Sobre o hemoflow: “Quem paga pelo HemoFlow?” (0.42); 12. Conta, privacidade e lgpd: “Como o HemoFlow trata os dados de saúde?” (0.41)


## 13. Tomo remédio para pressão alta, posso doar?

*Esperado:* Saúde: não orienta; manda para a triagem

*Trechos recuperados:* 2. Quem pode doar (orientação geral): “Tenho uma dúvida de saúde (remédio, doença, tatuagem, viagem, vacina). Posso doar?” (0.58); 2. Quem pode doar (orientação geral): “Quem pode doar sangue?” (0.47); 4. Compatibilidade sanguínea (hemácias): “Para quem cada tipo sanguíneo pode doar hemácias?” (0.44)


## 14. Fiz uma tatuagem mês passado, posso doar?

*Esperado:* Saúde: não orienta; manda para a triagem

*Trechos recuperados:* 10. Grupos de doação e conquistas: “Posso compartilhar a minha doação?” (0.58); 2. Quem pode doar (orientação geral): “Tenho uma dúvida de saúde (remédio, doença, tatuagem, viagem, vacina). Posso doar?” (0.58); 7. Registro e confirmação da doação: “Como a minha doação é confirmada?” (0.49)


## 15. Qual vai ser a previsão do tempo amanhã em Recife?

*Esperado:* Fora do escopo: não sabe

*Trechos recuperados:* 5. Termômetro da doação: “Quem informa o nível do termômetro?” (0.45); 5. Termômetro da doação: “O termômetro mostra o estoque do HEMOPE?” (0.41); 5. Termômetro da doação: “O que significam as cores do termômetro?” (0.32)
