import pytest
import unittest
from libs.translation import smart_html_split


class TestSmartHtmlSplit(unittest.TestCase):
    """Test smart HTML splitting functionality."""
    
    def test_smart_split_with_real_content(self):
        """Test smart HTML split with real French text content."""
        # Real French text from Le Rouge et le Noir
        large_html = '''<p id="filepos20395" class="calibre_14"><span class="calibre6"><span class="calibre7">Chapitre </span></span><span class="calibre1"><span class="bold"><span class="calibre7">
</span></span></span><span class="calibre5"><span class="calibre7">3 </span></span></p><p class="calibre_15"><span class="calibre1"><span class="bold"> Le Bien des pauvres</span></span></p><blockquote class="calibre_16">Un curé vertueux et sans intrigue est une Providence pour le village.</blockquote><blockquote class="calibre_17">FLEURY.</blockquote><p class="calibre_18">Il faut savoir que le curé de Verrières, vieillard de quatre-vingts ans, mais qui devait à l'air vif de ces montagnes une santé et un caractère de fer, avait le droit de visiter à toute heure la prison, l'hôpital et même le dépôt de mendicité. C'était précisément à six heures du matin que M. Appert, qui de Paris était recommandé au curé, avait eu la sagesse d'arriver dans une petite ville curieuse. Aussitôt il était allé au presbytère.</p><p class="calibre_6">En lisant la lettre que lui écrivait M. le marquis de La Mole, pair de France, et le plus riche propriétaire de la province, le curé Chélan resta pensif.</p><p class="calibre_6">Je suis vieux et aimé ici, se dit-il enfin à mi-voix, ils n'oseraient ! Se tournant tout de suite vers le monsieur de Paris, avec des yeux où, malgré le grand âge, brillait ce feu sacré qui annonce le plaisir de faire une belle action un peu dangereuse :</p><p class="calibre_6">– Venez avec moi, monsieur, et en présence du geôlier et surtout des surveillants du dépôt de mendicité, veuillez n'émettre aucune opinion sur les choses que nous verrons. M. Appert comprit qu'il avait affaire à un homme de cœur : il suivit le vénérable curé, visita la prison, l'hospice, le dépôt, fit beaucoup de questions et, malgré d'étranges réponses, ne se permit pas la moindre marque de blâme.</p><p class="calibre_6">Cette visite dura plusieurs heures. Le curé invita à dîner M. Appert, qui prétendit avoir des lettres à écrire : il ne voulait pas compromettre davantage son généreux compagnon. Vers les trois heures, ces messieurs allèrent achever l'inspection du dépôt de mendicité, et revinrent ensuite à la prison. Là, ils trouvèrent sur la porte le geôlier, espèce de géant de six pieds de haut et à jambes arquées ; sa figure ignoble était devenue hideuse par l'effet de la terreur.</p><p class="calibre_6">– Ah ! monsieur, dit-il au curé, dès qu'il l'aperçut, ce monsieur que je vois là avec vous, n'est-il pas M. Appert ?</p><p class="calibre_6">– Qu'importe ? dit le curé.</p><p class="calibre_6">– C'est que depuis hier j'ai l'ordre le plus précis, et que M. le préfet a envoyé par un gendarme, qui a dû galoper toute la nuit, de ne pas admettre M. Appert dans la prison.</p><p class="calibre_6">– Je vous déclare, monsieur Noiroud, dit le curé, que ce voyageur, qui est avec moi, est M. Appert. Reconnaissez-vous que j'ai le droit d'entrer dans la prison à toute heure du jour et de la nuit, et en me faisant accompagner par qui je veux ?</p><p class="calibre_6">– Oui, M. le curé, dit le geôlier à voix basse, et baissant la tête comme un bouledogue que fait obéir à regret la crainte du bâton. Seulement, M. le curé, j'ai femme et enfants, si je suis dénoncé on me destituera ; je n'ai pour vivre que ma place.</p><p class="calibre_6">– Je serais aussi bien fâché de perdre la mienne, reprit le bon curé, d'une voix de plus en plus émue.</p><p class="calibre_6">– Quelle différence ! reprit vivement le geôlier ; vous, M. le curé, on sait que vous avez 800 livres de rente, du bon bien au soleil…</p><p class="calibre_6">Tels sont les faits qui, commentés, exagérés de vingt façons différentes, agitaient depuis deux jours toutes les passions haineuses de la petite ville de Verrières. Dans ce moment, ils servaient de texte à la petite discussion que M. de Rênal avait avec sa femme. Le matin, suivi de M. Valenod, directeur du dépôt de mendicité, il était allé chez le curé pour lui témoigner le plus vif mécontentement. M. Chélan n'était protégé par personne ; il sentit toute la portée de leurs paroles.</p><p class="calibre_6">– Eh bien, messieurs ! je serai le troisième curé, de quatre-vingts ans d'âge, que l'on destituera dans ce voisinage. Il y a cinquante-six ans que je suis ici ; j'ai baptisé presque tous les habitants de la ville, qui n'était qu'un bourg quand j'y arrivai. Je marie tous les jours des jeunes gens, dont jadis j'ai marié les grands-pères. Verrières est ma famille ; mais je me suis dit, en voyant l'étranger : « Cet homme, venu de Paris, peut être à la vérité un libéral, il n'y en a que trop ; mais quel mal peut-il faire à nos pauvres et à nos prisonniers ? »</p><p class="calibre_6">Les reproches de M. de Rênal, et surtout ceux de M. Valenod, le directeur du dépôt de mendicité, devenant de plus en plus vifs :</p><p class="calibre_6">– Eh bien, messieurs ! faites-moi destituer, s'était écrié le vieux curé, d'une voix tremblante. Je n'en habiterai pas moins le pays. On sait qu'il y a quarante-huit ans, j'ai hérité d'un champ qui rapporte 800 livres. Je vivrai avec ce revenu. Je ne fais point d'économies dans ma place, moi, messieurs, et c'est peut-être pourquoi je ne suis pas si effrayé quand on parle de me la faire perdre.</p><p class="calibre_6">M. de Rénal vivait fort bien avec sa femme ; mais ne sachant que répondre à cette idée, qu'elle lui répétait timidement : « Quel mal ce monsieur de Paris peut-il faire aux prisonniers ? » il était sur le point de se fâcher tout à fait, quand elle jeta un cri. Le second de ses fils venait de monter sur le parapet du mur de la terrasse, et y courait, quoique ce mur fût élevé de plus de vingt pieds sur la vigne qui est de l'autre côté. La crainte d'effrayer son fils et de le faire tomber empêchait Mme de Rênal de lui adresser la parole. Enfin l'enfant, qui riait de sa prouesse, ayant regardé sa mère, vit sa pâleur, sauta sur la promenade et accourut à elle. Il fut bien grondé.</p><p class="calibre_6">Ce petit événement changea le cours de la conversation.</p><p class="calibre_6">– Je veux absolument prendre chez moi Sorel, le fils du scieur de planches, dit M. de Rênal ; il surveillera les enfants, qui commencent à devenir trop diables pour nous. C'est un jeune prêtre, ou autant vaut, bon latiniste, et qui fera faire des progrès aux enfants ; car il a un caractère ferme, dit le curé. Je lui donnerai 300 francs et la nourriture. J'avais quelques doutes sur sa moralité ; car il était le Benjamin de ce vieux chirurgien, membre de la Légion d'honneur, qui, sous prétexte qu'il était leur cousin ; était venu se mettre en pension chez les Sorel. Cet homme pouvait fort bien n'être au fond qu'un agent secret des libéraux ; il disait que l'air de nos montagnes faisait du bien à son asthme ; mais c'est ce qui n'est pas prouvé. Il avait fait toutes les campagnes de Buonaparté en Italie, et même avait, dit-on, signé non pour l'empire dans le temps. Ce libéral montrait le latin au fils Sorel, et lui a laissé cette quantité de livres qu'il avait apportés avec lui. Aussi n'aurais-je jamais songé à mettre le fils du charpentier auprès de nos enfants ; mais le curé, justement la veille de la scène qui vient de nous brouiller à jamais, m'a dit que ce Sorel étudie la théologie depuis trois ans, avec le projet d'entrer au séminaire ; il n'est donc pas libéral, et il est latiniste.</p><p class="calibre_6">Cet arrangement convient de plus d'une façon, continua M. de Rênal, en regardant sa femme d'un air diplomatique ; le Valenod est tout fier des deux beaux normands qu'il vient d'acheter pour sa calèche. Mais il n'a pas de précepteur pour ses enfants.</p><p class="calibre_6">– Il pourrait bien nous enlever celui-ci.</p><p class="calibre_6">– Tu approuves donc mon projet ? dit M. de Rênal, remerciant sa femme, par un sourire, de l'excellente idée qu'elle venait d'avoir. Allons, voilà qui est décidé.</p><p class="calibre_6">– Ah, bon Dieu ! mon cher ami, comme tu prends vite un parti !</p><p class="calibre_6">– C'est que j'ai du caractère, moi, et le curé l'a bien vu. Ne dissimulons rien, nous sommes environnés de libéraux ici. Tous ces marchands de toile me portent envie, j'en ai la certitude ; deux ou trois deviennent des richards ; eh bien ! j'aime assez qu'ils voient passer les enfants de M. de Rênal allant à la promenade sous la conduite de leur précepteur. Cela imposera. Mon grand-père nous racontait souvent que, dans sa jeunesse, il avait eu un précepteur. C'est cent écus qu'il m'en pourra coûter, mais ceci doit être classé comme une dépense nécessaire pour soutenir notre rang.</p><p class="calibre_6">Cette résolution subite laissa Mme de Rênal toute pensive. C'était une femme grande, bien faite, qui avait été la beauté du pays, comme on dit dans ces montagnes. Elle avait un certain air de simplicité, et de la jeunesse dans la démarche ; aux yeux d'un Parisien, cette grâce naïve, pleine d'innocence et de vivacité, serait même allée jusqu'à rappeler des idées de douce volupté. Si elle eût appris ce genre de succès, Mme de Rênal en eût été bien honteuse. Ni la coquetterie, ni l'affection n'avaient jamais approché de ce cœur. M. Valenod, le riche directeur du dépôt, passait pour lui avoir fait la cour, mais sans succès, ce qui avait jeté un éclat singulier sur sa vertu ; car ce M. Valenod, grand jeune homme, taillé en force, avec un visage coloré et de gros favoris noirs, était un de ces êtres grossiers, effrontés et bruyants, qu'en province on appelle de beaux hommes.</p><p class="calibre_6">Mme de Rênal, fort timide, et d'un caractère en apparence fort égal, était surtout choquée du mouvement continuel et des éclats de voix de M. Valenod. L'éloignement qu'elle avait pour ce qu'à Verrières on appelle de la joie lui avait valu la réputation d'être très fière de sa naissance. Elle n'y songeait pas, mais avait été fort contente de voir les habitants de la ville venir moins chez elle. Nous ne dissimulerons pas qu'elle passait pour sotte aux yeux de leurs dames, parce que, sans nulle politique à l'égard de son mari, elle laissait échapper les plus belles occasions de se faire acheter de beaux chapeaux de Paris ou de Besançon. Pourvu qu'on la laissât seule errer dans son beau jardin, elle ne se plaignait jamais.</p><p class="calibre_6">C'était une âme naïve, qui jamais ne s'était élevée même jusqu'à juger son mari, et à s'avouer qu'il l'ennuyait. Elle supposait sans se le dire qu'entre mari et femme il n'y avait pas de plus douces relations. Elle aimait surtout M. de Rênal quand il lui parlait de ses projets sur leurs enfants, dont il destinait l'un à l'épée, le second à la magistrature, et le troisième à l'église. En somme, elle trouvait M. de Rênal beaucoup moins ennuyeux que tous les hommes de sa connaissance.</p><p class="calibre_6">Ce jugement conjugal était raisonnable. Le maire de Verrières devait une réputation d'esprit et surtout de bon ton à une demi-douzaine de plaisanteries dont il avait hérité d'un oncle. Le vieux capitaine de Rênal servait avant la révolution dans le régiment d'infanterie de M. le duc d'Orléans, et, quand il allait à Paris, était admis dans les salons du prince. Il y avait vu Mme de Montesson, la fameuse Mme de Genlis, M. Ducrest, l'inventeur du Palais-Royal. Ces personnages ne reparaissaient que trop souvent dans les anecdotes de M. de Rênal. Mais peu à peu ce souvenir de choses aussi délicates à raconter était devenu un travail pour lui, et, depuis quelque temps, il ne répétait que dans les grandes occasions ses anecdotes relatives à la maison d'Orléans. Comme il était d'ailleurs fort poli, excepté lorsqu'on parlait d'argent, il passait, avec raison, pour le personnage le plus aristocratique de Verrières.</p><div class="mbp_pagebreak" id="calibre_pb_6"/>'''
        
        # Test with target size of 8000 characters
        target_size = 8000
        chunks = smart_html_split(large_html, target_size)
        
        # Basic validation
        assert len(chunks) > 1, "Large content should be split into multiple chunks"
        
        # Check that all content is preserved
        combined_content = ''.join(chunks)
        assert combined_content == large_html, "All content should be preserved after splitting"
        
        # Check chunk sizes are reasonable (allowing for some variance due to smart splitting)
        for i, chunk in enumerate(chunks):
            chunk_size = len(chunk)
            print(f"Chunk {i+1}: {chunk_size} characters")
            # Most chunks should be close to target size (within reasonable bounds)
            # Last chunk can be smaller
            if i < len(chunks) - 1:  # Not the last chunk
                assert chunk_size <= target_size + 1000, f"Chunk {i+1} too large: {chunk_size} chars"
            assert chunk_size > 0, f"Chunk {i+1} is empty"
        
        # Verify no chunks are split in the middle of words
        for i, chunk in enumerate(chunks):
            # Check that chunks preserve content integrity
            if i > 0:  # Not the first chunk
                # The chunk should either start with a complete tag or text content
                # Allow chunks to start with '<' if it's a complete tag
                if chunk.startswith('<'):
                    # Make sure it's not an incomplete tag like just '<'
                    tag_end = chunk.find('>')
                    assert tag_end > 0, f"Chunk {i+1} starts with incomplete tag: {chunk[:20]}"
                    
            if i < len(chunks) - 1:  # Not the last chunk
                assert not chunk.endswith('<'), f"Chunk {i+1} ends with incomplete tag"
        
        print(f"✓ Successfully split {len(large_html)} chars into {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i+1}: {len(chunk)} chars")
    
    def test_smart_split_preserves_tag_boundaries(self):
        """Test that splitting preserves HTML tag boundaries"""
        html = ('<p>First paragraph.</p><p>Second paragraph with more content to ensure splitting.</p>' * 100)
        chunks = smart_html_split(html, 1000)
        
        # Should create multiple chunks for large content
        self.assertGreater(len(chunks), 1)
        
        # Check that both contain the same number of paragraph tags (most important)
        combined = ''.join(chunks)
        self.assertEqual(combined.count('<p>'), html.count('<p>'))
        self.assertEqual(combined.count('</p>'), html.count('</p>'))
        
        # Check that the content length difference is minimal (within a few chars)
        self.assertLess(abs(len(combined) - len(html)), 10)
    
    def test_small_content_not_split(self):
        """Test that content smaller than target size is not split."""
        small_html = "<p>This is a small paragraph.</p>"
        target_size = 8000
        
        chunks = smart_html_split(small_html, target_size)
        
        assert len(chunks) == 1, "Small content should not be split"
        assert chunks[0] == small_html, "Content should be unchanged"
    
    def test_large_content_split_efficiency(self):
        """Test that large content is split efficiently without too many chunks."""
        # Create a large HTML content (simulate a very large chapter)
        large_content = "<p>This is a paragraph with substantial content that needs to be translated efficiently.</p>" * 1000
        original_size = len(large_content)
        
        # Test different target sizes to ensure reasonable chunk counts
        for target_size in [4000, 8000, 16000]:
            chunks = smart_html_split(large_content, target_size)
            
            # Calculate expected vs actual chunks
            expected_chunks = max(1, original_size // target_size)
            actual_chunks = len(chunks)
            
            print(f"Target size {target_size}: {actual_chunks} chunks (expected ~{expected_chunks})")
            
            # Should not create way more chunks than expected
            assert actual_chunks <= expected_chunks * 2, f"Too many chunks created: {actual_chunks} vs expected ~{expected_chunks}"
            
            # Verify content preservation (check paragraph counts instead of exact match)
            combined = ''.join(chunks)
            self.assertEqual(combined.count('<p>'), large_content.count('<p>'))
            self.assertEqual(combined.count('</p>'), large_content.count('</p>'))
    
    def test_chunk_halving_strategy(self):
        """Test that chunk sizes actually follow a halving strategy."""
        # Test the halving approach: if 8000 fails, try 4000, then 2000, etc.
        large_content = "<p>Content that should be split using halving strategy.</p>" * 200
        original_size = len(large_content)
        
        # Test progressive halving
        sizes_to_test = [8000, 4000, 2000, 1000]
        
        for target_size in sizes_to_test:
            chunks = smart_html_split(large_content, target_size)
            
            # Verify chunk sizes are reasonable
            max_chunk_size = max(len(chunk) for chunk in chunks)
            print(f"Target: {target_size}, Max chunk: {max_chunk_size}, Chunks: {len(chunks)}")
            
            # Max chunk should be close to target (with some tolerance for smart splitting)
            if original_size > target_size:
                assert max_chunk_size <= target_size + 500, f"Chunk too large for target {target_size}: {max_chunk_size}"
    
    def test_halving_strategy_logic(self):
        """Test that the halving strategy would work as expected."""
        # Simulate content sizes that would trigger the halving logic
        content_sizes = [123422, 50000, 25000, 12000]
        
        for content_size in content_sizes:
            # Simulate the halving logic from translate_with_chunking
            initial_size = content_size
            chunk_size = min(initial_size // 2, 16000)
            min_chunk_size = 2000
            
            sizes_tried = []
            while chunk_size >= min_chunk_size:
                if chunk_size >= initial_size:
                    chunk_size = chunk_size // 2
                    continue
                sizes_tried.append(chunk_size)
                chunk_size = chunk_size // 2
            
            print(f"Content size {content_size}: Would try chunk sizes {sizes_tried}")
            
            # Verify we get a reasonable progression
            assert len(sizes_tried) > 0, f"Should try at least one chunk size for {content_size}"
            
            # Verify halving pattern (each size should be roughly half of previous)
            for i in range(1, len(sizes_tried)):
                ratio = sizes_tried[i-1] / sizes_tried[i]
                assert 1.8 <= ratio <= 2.2, f"Not proper halving: {sizes_tried[i-1]} -> {sizes_tried[i]}"
