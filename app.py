from flask import Flask, render_template, request,jsonify
import io
import pandas as pd
from datetime import datetime
import csv
import networkx
import json
import time


app = Flask(__name__)
app.debug = True
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/', methods=['POST'])
def upload_file():
    print(request.files)
    if request.files['file'].filename == '':
        return 'No selected file. Go back and upload a file.'
    else:
        uploaded_file = request.files['file']
        stream = io.StringIO(uploaded_file.stream.read().decode("UTF8"))
        #read the uploaded file
        global data
        data = pd.read_csv(stream, sep = ";")
        #oldest date of the dataset
        oldest = min(data['Timestamp'])
        #youngest date of the dataset
        youngest = max(data['Timestamp'])
        return render_template('app.html')

@app.route('/test/', methods=['GET', 'POST'])
def main_interface():
    
    if request.method == "POST":
        response = request.get_json()
        #request startDate and endDate
        startDate = datetime(*(time.strptime(response["a"],"%Y-%m-%dT%H:%M:%S.%f%z")[0:6]))
        endDate = datetime(*(time.strptime(response["b"],"%Y-%m-%dT%H:%M:%S.%f%z")[0:6]))

        
        for i in range(len(data)):
            data.loc[i, "Timestamp"]  = pd.to_datetime(data.loc[i, "Timestamp"],format="%Y-%m-%d %H:%M:%S")


        #dataset within the time interval
        df = data[(data['Timestamp'] >= startDate) & (data['Timestamp'] <= endDate)]
        
        #turn the df dataframe into dictonary
        d = {}
        for i in df["CaseID"].unique():
            d[i] = [{df["Role"][j]: df["Activities"][j]} for j in df[df["CaseID"]==i].index]
            
        if len(d) != 0:
            #create dictionary that contains
            #which user communicates with which one and how many times
            users = dict()
            for key in d:
                for i in range(0, len(d[key])-1):
                    #the user
                    ui = list(d[key][i].keys())[0]
                    #the user that the previous user communicates with
                    uj = list(d[key][i+1].keys())[0]
                    #add the users in dictionary
                    if ui not in users:
                        users[ui] = dict() 
                    if uj not in users[ui]:
                        users[ui][uj] = 0
                    users[ui][uj] += 1
     
            #create the dictionary which contains
            #the total nr of activities of each user
            nrActUser = dict()
            for key in d:
                for i in range(0, len(d[key])):
                    ai = list(d[key][i].keys())[0]
                    if ai not in nrActUser:
                        nrActUser[ai] = 0
                    nrActUser[ai] += 1 
     
            #build graph
            import pygraphviz as pgv
            G = pgv.AGraph(strict=False, directed=True)
            G.graph_attr['rankdir'] = 'LR'
            G.node_attr['shape'] = 'circle'
            for ai in nrActUser:
                text = ai + '\n(' + str(nrActUser[ai]) + ')' 
                G.add_node(ai, label=text)

            #define the color of the graph, such that it changes the more activities a user has
            x_min = min(nrActUser.values())
            x_max = max(nrActUser.values())
            for ai in nrActUser:
                text = ai + '\n(' + str(nrActUser[ai]) + ')'
                if x_max-x_min == 0:
                    gray = int(float(x_max - nrActUser[ai]) / float(1) * 100.)
                else:
                    gray = int(float(x_max - nrActUser[ai]) / float(x_max - x_min) * 100.)
                fill = 'gray' + str(gray)
                font = 'black'
                if gray < 50:
                    font = 'white'
                G.add_node(ai, label=text, style='filled', fillcolor=fill, fontcolor=font, width = 2)



            #define the edge thickness, which gets thicker the more activities a user has      
            values = [users[ai][aj] for ai in users for aj in users[ai]]
            x_min = min(values)
            x_max = max(values)
            y_min = 1.0
            y_max = 3.0

            for ai in users:
                for aj in users[ai]:
                    x = users[ai][aj]
                    if x_max-x_min == 0:
                        y = y_min + (y_max-y_min) * float(x-x_min)
                    else:
                        y = y_min + (y_max-y_min) * float(x-x_min) / float(x_max-x_min)
                    G.add_edge(ai, aj, label=x, penwidth=y)
            #draw graph
            filename = 'static/Network  ' + str(startDate)+' -- '+str(endDate)+'.png'
            G.draw(filename, prog='dot')

            #build a networkx graph to calculate the complexity measures
            import networkx as nx
            dff = pd.DataFrame()
            for i in users:
                for j, k in users[i].items():
                    row = []
                    row.append([i,j,k])
                    dff = dff.append(row, ignore_index=True)
            dff.columns =['Source', 'Target', 'Weight'] 
            N = nx.from_pandas_edgelist(dff, 'Source', 'Target', 'Weight', create_using=nx.DiGraph())

            #calculate the complexity measures
            nrOfEdges =  N.number_of_edges()
            nrOfNodes =  N.number_of_nodes()
            density =  round(nx.density(N),3)
            transitivity = round(nx.transitivity(N),3)
            btwCentrality = nx.betweenness_centrality(N)
            minbV = round(min(zip(btwCentrality.values(), btwCentrality.keys()))[0],3)
            minbK = min(zip(btwCentrality.values(), btwCentrality.keys()))[1]
            maxbV = round(max(zip(btwCentrality.values(), btwCentrality.keys()))[0],3)
            maxbK = max(zip(btwCentrality.values(), btwCentrality.keys()))[1]
            
            clsCentrality = nx.closeness_centrality(N)
            mincV = round(min(zip(clsCentrality.values(), clsCentrality.keys()))[0],3)
            mincK = min(zip(clsCentrality.values(), clsCentrality.keys()))[1]
            maxcV = round(max(zip(clsCentrality.values(), clsCentrality.keys()))[0],3)
            maxcK = max(zip(clsCentrality.values(), clsCentrality.keys()))[1]
            
            #return the response as json
            return jsonify({'nrOfEdges' : nrOfEdges,
                            'nrOfNodes' : nrOfNodes,
                            'density': density,
                            'transitivity': transitivity,
                            'minbK' : minbK,
                            'minbV' : minbV,
                            'maxbK' : maxbK,
                            'maxbV' : maxbV,
                            'mincK' : mincK,
                            'mincV' : mincV,
                            'maxcK' : maxcK,
                            'maxcV' : maxcV,
                            'clsCentrality' : clsCentrality,
                            'filename': filename })
        else:
            return jsonify({'p' : 'No communication network during this time'})
    
@app.after_request
def add_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')

    return response
if __name__ == '__main__':
    app.run(debug=True)
